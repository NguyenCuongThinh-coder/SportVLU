import os
import re
import sqlite3
import tempfile
import unittest
import hashlib
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

_bootstrap = tempfile.TemporaryDirectory(prefix='sportslot-test-bootstrap-')
os.environ['SPORTSLOT_DB_PATH'] = os.path.join(_bootstrap.name, 'bootstrap.sqlite3')

import app as sport_app
from werkzeug.security import check_password_hash, generate_password_hash


class SportSlotTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sportslot-test-')
        sport_app.DB_PATH = os.path.join(self.temp.name, 'test.sqlite3')
        sport_app.init_db()
        sport_app.app.config.update(TESTING=True, SECRET_KEY='test-secret-key')
        with sport_app.db() as conn:
            self.owner = conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)', ('Owner A','owner-a@example.test',generate_password_hash('password123'),'owner')).lastrowid
            self.other_owner = conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)', ('Owner B','owner-b@example.test',generate_password_hash('password123'),'owner')).lastrowid
            self.player = conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)', ('Player A','player-a@example.test',generate_password_hash('password123'),'player')).lastrowid
            self.other_player = conn.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)', ('Player B','player-b@example.test',generate_password_hash('password123'),'player')).lastrowid
            self.court = conn.execute('INSERT INTO courts(name,sport,area,price,owner_id) VALUES(?,?,?,?,?)', ('Owned Court','Cầu lông','Quận 1','120.000',self.owner)).lastrowid
            self.other_court = conn.execute('INSERT INTO courts(name,sport,area,price,owner_id) VALUES(?,?,?,?,?)', ('Other Court','Pickleball','Quận 3','150.000',self.other_owner)).lastrowid
        self.client = sport_app.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def csrf(self, client=None, path='/'):
        response=(client or self.client).get(path)
        match=re.search(rb'name="_csrf_token" value="([^"]+)"',response.data)
        self.assertIsNotNone(match, f'No CSRF token in {path}')
        return match.group(1).decode()

    def login(self, email, client=None, next_path=None):
        client=client or self.client
        path='/login'+(f'?next={next_path}' if next_path else '')
        token=self.csrf(client,path)
        return client.post('/login',data={'_csrf_token':token,'email':email,'password':'password123','next':next_path or ''},follow_redirects=False)

    def test_routes_render_and_access_control(self):
        for path in ('/','/courts','/courts?sport=Pickleball','/login','/register'):
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertEqual(self.client.get(f'/courts/{self.court}').status_code,200)
        self.assertEqual(self.client.get('/courts/999999').status_code,404)
        self.assertEqual(self.client.get('/owner').status_code,302)

    def test_register_hashes_password_and_login_returns_to_requested_path(self):
        token=self.csrf(path='/register')
        response=self.client.post('/register',data={'_csrf_token':token,'name':'New Player','email':'new@example.test','password':'strongpass1','confirm_password':'strongpass1','role':'player'})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            user=conn.execute('SELECT password_hash FROM users WHERE email=?',('new@example.test',)).fetchone()
        self.assertTrue(check_password_hash(user['password_hash'],'strongpass1'))
        other=sport_app.app.test_client()
        response=self.login('player-a@example.test',other,'/my-bookings')
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.headers['Location'],'/my-bookings')
        external=sport_app.app.test_client()
        response=self.login('player-a@example.test',external,'//evil.example')
        self.assertEqual(response.headers['Location'],'/')

    def test_csrf_is_required_for_mutations(self):
        response=self.client.post('/login',data={'email':'x','password':'y'})
        self.assertEqual(response.status_code,400)

    def test_logout_clears_the_session(self):
        self.login('player-a@example.test')
        token=self.csrf(self.client,'/my-bookings')
        response=self.client.post('/logout',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.get('/my-bookings').status_code,302)

    def test_profile_update_and_password_change(self):
        self.login('player-a@example.test')
        token=self.csrf(path='/profile')
        response=self.client.post('/profile',data={'_csrf_token':token,'name':'Player Updated','phone':'0912345678'})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            row=conn.execute('SELECT name,phone FROM users WHERE id=?',(self.player,)).fetchone()
        self.assertEqual((row['name'],row['phone']),('Player Updated','0912345678'))
        token=self.csrf(path='/profile')
        response=self.client.post('/profile/password',data={'_csrf_token':token,'current_password':'password123','new_password':'newpassword456','confirm_password':'newpassword456'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.headers['Location'],'/login')
        with sport_app.db() as conn:
            password_hash=conn.execute('SELECT password_hash FROM users WHERE id=?',(self.player,)).fetchone()['password_hash']
        self.assertTrue(check_password_hash(password_hash,'newpassword456'))

    def test_password_reset_token_is_one_time(self):
        raw_token='single-use-reset-token'
        expires=(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat()
        with sport_app.db() as conn:
            conn.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)',(self.player,hashlib.sha256(raw_token.encode()).hexdigest(),expires))
        response=self.client.get(f'/reset-password/{raw_token}')
        self.assertEqual(response.status_code,200)
        token=self.csrf(path=f'/reset-password/{raw_token}')
        response=self.client.post(f'/reset-password/{raw_token}',data={'_csrf_token':token,'password':'resetpassword456','confirm_password':'resetpassword456'})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            password_hash=conn.execute('SELECT password_hash FROM users WHERE id=?',(self.player,)).fetchone()['password_hash']
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM password_reset_tokens WHERE user_id=?',(self.player,)).fetchone()[0],0)
        self.assertTrue(check_password_hash(password_hash,'resetpassword456'))
        self.assertEqual(self.client.get(f'/reset-password/{raw_token}').status_code,302)

    def test_forgot_password_sends_reset_link_without_revealing_account_existence(self):
        client=sport_app.app.test_client()
        token=self.csrf(client,'/forgot-password')
        smtp={'SPORTSLOT_SMTP_HOST':'smtp.example.test','SPORTSLOT_SMTP_FROM':'SportSlot <noreply@example.test>','SPORTSLOT_PUBLIC_URL':'https://sportslot.example.test'}
        with patch.dict(os.environ,smtp), patch.object(sport_app,'send_email',return_value=True) as send:
            response=client.post('/forgot-password',data={'_csrf_token':token,'email':'player-a@example.test'})
        self.assertEqual(response.status_code,302)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0],'player-a@example.test')
        self.assertIn('/reset-password/',send.call_args.args[2])
        token=self.csrf(client,'/forgot-password')
        with patch.dict(os.environ,smtp), patch.object(sport_app,'send_email',return_value=True) as send:
            response=client.post('/forgot-password',data={'_csrf_token':token,'email':'unknown@example.test'})
        self.assertEqual(response.status_code,302)
        send.assert_not_called()

    def test_booking_validates_and_serializes_same_slot_requests(self):
        date_text=(sport_app.local_today()+timedelta(days=1)).isoformat()
        clients=[sport_app.app.test_client(),sport_app.app.test_client()]
        tokens=[]
        for client in clients:
            self.login('player-a@example.test',client)
            tokens.append(self.csrf(client,f'/book/{self.court}'))
        def submit(item):
            client,token=item
            return client.post(f'/book/{self.court}',data={'_csrf_token':token,'play_date':date_text,'time_slot':'18:00–19:00','customer_name':'Player A','phone':'0900000000'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(submit,zip(clients,tokens)))
        self.assertEqual(sum(response.status_code==302 for response in responses),1)
        self.assertTrue(all(response.status_code in (200,302) for response in responses))
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM bookings WHERE court_id=? AND play_date=?',(self.court,date_text)).fetchone()[0],1)
        bad=self.client
        self.login('player-a@example.test',bad)
        token=self.csrf(bad,f'/book/{self.court}')
        response=bad.post(f'/book/{self.court}',data={'_csrf_token':token,'play_date':'tomorrow','time_slot':'18:00–19:00','customer_name':'Player A','phone':'0900000000'})
        self.assertEqual(response.status_code,200)

    def test_booking_availability_only_blocks_pending_and_confirmed_slots(self):
        day=(sport_app.local_today()+timedelta(days=2)).isoformat()
        with sport_app.db() as conn:
            conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)',(self.court,self.player,day,'18:00–19:00','Player A','0900000000','pending'))
            conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)',(self.court,self.player,day,'19:00–20:00','Player A','0900000000','cancelled'))
        response=self.client.get(f'/api/courts/{self.court}/availability?date={day}')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['booked_slots'],['18:00–19:00'])
        self.assertIn('19:00–20:00',response.json['available_slots'])
        self.assertEqual(self.client.get(f'/api/courts/{self.court}/availability?date=invalid').status_code,400)

    def test_new_booking_and_status_change_send_email_notifications(self):
        day=(sport_app.local_today()+timedelta(days=1)).isoformat()
        player=sport_app.app.test_client(); self.login('player-a@example.test',player)
        token=self.csrf(player,f'/book/{self.court}')
        form={'_csrf_token':token,'play_date':day,'time_slot':'18:00–19:00','customer_name':'Player A','phone':'0900000000'}
        with patch.object(sport_app,'send_email',return_value=True) as send:
            response=player.post(f'/book/{self.court}',data=form)
        self.assertEqual(response.status_code,302)
        self.assertEqual(send.call_args.args[0],'owner-a@example.test')
        with sport_app.db() as conn:
            booking_id=conn.execute('SELECT id FROM bookings WHERE court_id=? AND play_date=?',(self.court,day)).fetchone()['id']
        owner=sport_app.app.test_client(); self.login('owner-a@example.test',owner)
        token=self.csrf(owner,'/owner')
        with patch.object(sport_app,'send_email',return_value=True) as send:
            response=owner.post(f'/owner/bookings/{booking_id}/confirm',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        self.assertEqual(send.call_args.args[0],'player-a@example.test')
        self.assertIn('đã xác nhận',send.call_args.args[2])

    def test_booking_history_is_private_and_only_players_can_cancel(self):
        with sport_app.db() as conn:
            booking_id=conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone) VALUES(?,?,?,?,?,?)',(self.court,self.player,(sport_app.local_today()+timedelta(days=1)).isoformat(),'18:00–19:00','Player A','0900000000')).lastrowid
        self.login('player-b@example.test')
        self.assertNotIn(b'Owned Court',self.client.get('/my-bookings').data)
        player=sport_app.app.test_client(); self.login('player-a@example.test',player)
        self.assertIn(b'Owned Court',player.get('/my-bookings').data)
        token=self.csrf(player,'/my-bookings')
        response=player.post(f'/my-bookings/{booking_id}/cancel',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT status FROM bookings WHERE id=?',(booking_id,)).fetchone()['status'],'cancelled')
        owner=sport_app.app.test_client(); self.login('owner-a@example.test',owner)
        owner_token=self.csrf(owner,'/owner')
        response=owner.post(f'/my-bookings/{booking_id}/cancel',data={'_csrf_token':owner_token})
        self.assertEqual(response.status_code,403)

    def test_player_can_cancel_confirmed_future_booking(self):
        future=(sport_app.local_today()+timedelta(days=2)).isoformat()
        with sport_app.db() as conn:
            booking_id=conn.execute("INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)",(self.court,self.player,future,'18:00–19:00','Player A','0900000000','confirmed')).lastrowid
        client=sport_app.app.test_client(); self.login('player-a@example.test',client)
        token=self.csrf(client,'/my-bookings')
        response=client.post(f'/my-bookings/{booking_id}/cancel',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT status FROM bookings WHERE id=?',(booking_id,)).fetchone()['status'],'cancelled')

    def test_legacy_schema_migrates_without_losing_data_and_creates_backup(self):
        legacy_dir=tempfile.TemporaryDirectory(prefix='sportslot-legacy-')
        legacy_path=os.path.join(legacy_dir.name,'legacy.sqlite3')
        conn=sqlite3.connect(legacy_path)
        conn.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,phone TEXT,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'player',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE courts(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,sport TEXT NOT NULL,area TEXT NOT NULL,price TEXT NOT NULL,lat REAL,lng REAL,description TEXT,owner_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE bookings(id INTEGER PRIMARY KEY AUTOINCREMENT,court_id INTEGER NOT NULL,user_id INTEGER NOT NULL,play_date TEXT NOT NULL,time_slot TEXT NOT NULL,customer_name TEXT NOT NULL,phone TEXT NOT NULL,note TEXT,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO users(name,email,password_hash,role) VALUES('Kept User','kept@example.test','hash','owner');
            INSERT INTO courts(name,sport,area,price,owner_id) VALUES('Kept Court','Cầu lông','Quận 1','120.000',1);
            INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone) VALUES(1,1,'2030-01-01','18:00–19:00','Kept Customer','0900000000');
        ''')
        conn.commit(); conn.close()
        old_path=sport_app.DB_PATH
        try:
            sport_app.DB_PATH=legacy_path
            sport_app.init_db()
            with sport_app.db() as migrated:
                self.assertEqual(migrated.execute('SELECT name,is_active FROM courts WHERE id=1').fetchone()['name'],'Kept Court')
                self.assertEqual(migrated.execute('SELECT is_active FROM courts WHERE id=1').fetchone()['is_active'],1)
                self.assertEqual(migrated.execute('SELECT COUNT(*) FROM bookings').fetchone()[0],1)
            with sqlite3.connect(legacy_path+'.pre-migration.bak') as backup:
                self.assertEqual(backup.execute('SELECT name FROM courts WHERE id=1').fetchone()[0],'Kept Court')
                self.assertNotIn('is_active',{row[1] for row in backup.execute('PRAGMA table_info(courts)')})
        finally:
            sport_app.DB_PATH=old_path
            legacy_dir.cleanup()

    def test_owner_booking_access_and_status_transitions_are_scoped(self):
        day=(sport_app.local_today()+timedelta(days=1)).isoformat()
        with sport_app.db() as conn:
            own=conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone) VALUES(?,?,?,?,?,?)',(self.court,self.player,day,'18:00–19:00','Private Player','0900000000')).lastrowid
            foreign=conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone) VALUES(?,?,?,?,?,?)',(self.other_court,self.other_player,day,'19:00–20:00','Other Private Player','0900000001')).lastrowid
        client=sport_app.app.test_client(); self.login('owner-a@example.test',client)
        response=client.get('/owner')
        self.assertIn(b'player-a@example.test',response.data)
        self.assertNotIn(b'player-b@example.test',response.data)
        token=self.csrf(client,'/owner')
        response=client.post(f'/owner/bookings/{foreign}/confirm',data={'_csrf_token':token})
        self.assertEqual(response.status_code,403)
        response=client.post(f'/owner/bookings/{own}/confirm',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        response=client.post(f'/owner/bookings/{own}/reject',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT status FROM bookings WHERE id=?',(own,)).fetchone()['status'],'confirmed')

    def test_owner_rejection_is_distinct_and_completion_requires_elapsed_booking(self):
        tomorrow=(sport_app.local_today()+timedelta(days=1)).isoformat()
        yesterday=(sport_app.local_today()-timedelta(days=1)).isoformat()
        with sport_app.db() as conn:
            rejected=conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone) VALUES(?,?,?,?,?,?)',(self.court,self.player,tomorrow,'17:00–18:00','Player A','0900000000')).lastrowid
            future=conn.execute("INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)",(self.court,self.player,tomorrow,'18:00–19:00','Player A','0900000000','confirmed')).lastrowid
            elapsed=conn.execute("INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)",(self.court,self.player,yesterday,'18:00–19:00','Player A','0900000000','confirmed')).lastrowid
        client=sport_app.app.test_client(); self.login('owner-a@example.test',client)
        token=self.csrf(client,'/owner')
        self.assertEqual(client.post(f'/owner/bookings/{rejected}/reject',data={'_csrf_token':token}).status_code,302)
        self.assertEqual(client.post(f'/owner/bookings/{future}/complete',data={'_csrf_token':token}).status_code,302)
        self.assertEqual(client.post(f'/owner/bookings/{elapsed}/complete',data={'_csrf_token':token}).status_code,302)
        with sport_app.db() as conn:
            states={row['id']:row['status'] for row in conn.execute('SELECT id,status FROM bookings WHERE id IN (?,?,?)',(rejected,future,elapsed))}
        self.assertEqual(states,{rejected:'rejected',future:'confirmed',elapsed:'completed'})

    def test_owner_can_add_edit_deactivate_and_reactivate_own_court(self):
        client=sport_app.app.test_client(); self.login('owner-a@example.test',client)
        token=self.csrf(client,'/owner')
        form={'_csrf_token':token,'name':'New Court','sport':'Pickleball','area':'Quận 5','price':'200.000','lat':'10.7','lng':'106.6','description':'Court description'}
        response=client.post('/owner/courts/add',data=form)
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            court_id=conn.execute('SELECT id FROM courts WHERE name=?',('New Court',)).fetchone()['id']
        form.update(name='Updated Court',price='210000')
        response=client.post(f'/owner/courts/{court_id}/edit',data=form)
        self.assertEqual(response.status_code,302)
        self.assertEqual(client.get('/courts?q=Updated').status_code,200)
        foreign=client.post(f'/owner/courts/{self.other_court}/edit',data=form)
        self.assertEqual(foreign.status_code,404)
        response=client.post(f'/owner/courts/{court_id}/delete',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT is_active FROM courts WHERE id=?',(court_id,)).fetchone()['is_active'],0)
        self.assertEqual(client.post(f'/owner/courts/{court_id}/activate',data={'_csrf_token':token}).status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT is_active FROM courts WHERE id=?',(court_id,)).fetchone()['is_active'],1)

    def test_owner_court_form_rejects_invalid_price_and_coordinates(self):
        client=sport_app.app.test_client(); self.login('owner-a@example.test',client)
        token=self.csrf(client,'/owner')
        form={'_csrf_token':token,'name':'Invalid Court','sport':'Cầu lông','area':'Quận 5','price':'free','lat':'10.7','lng':'106.6'}
        client.post('/owner/courts/add',data=form)
        form.update(name='Invalid Coordinates',price='120.000',lat='91')
        client.post('/owner/courts/add',data=form)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM courts WHERE name IN ('Invalid Court','Invalid Coordinates')").fetchone()[0],0)

    def test_owner_cannot_deactivate_court_with_pending_or_confirmed_bookings(self):
        day=(sport_app.local_today()+timedelta(days=1)).isoformat()
        with sport_app.db() as conn:
            conn.execute('INSERT INTO bookings(court_id,user_id,play_date,time_slot,customer_name,phone,status) VALUES(?,?,?,?,?,?,?)',(self.court,self.player,day,'18:00–19:00','Player A','0900000000','pending'))
        client=sport_app.app.test_client(); self.login('owner-a@example.test',client)
        token=self.csrf(client,'/owner')
        response=client.post(f'/owner/courts/{self.court}/delete',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT is_active FROM courts WHERE id=?',(self.court,)).fetchone()['is_active'],1)
            conn.execute("UPDATE bookings SET status='confirmed' WHERE court_id=?",(self.court,))
        response=client.post(f'/owner/courts/{self.court}/delete',data={'_csrf_token':token})
        self.assertEqual(response.status_code,302)
        with sport_app.db() as conn:
            self.assertEqual(conn.execute('SELECT is_active FROM courts WHERE id=?',(self.court,)).fetchone()['is_active'],1)


if __name__ == '__main__':
    unittest.main()
