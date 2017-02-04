from flask import Flask, request, render_template, session, redirect, url_for, make_response
from datetime import datetime
from dateutil import tz
from decimal import *
import MySQLdb, hashlib, os, redis

app = Flask(__name__)
app.secret_key = "1|D0N'T|W4NT|TH15|T0|3E|R4ND0M"

@app.route('/', methods=['POST','GET'])
def register():
	if 'username' in session:
		return render_template('index.html', username = session['username'])
		
	if request.method == 'POST':
		db = MySQLdb.connect("localhost","root","root","splitwise")
		cursor = db.cursor()
		
		username = request.form['username']
		password = request.form['password']
		type = request.form['type']
		
		if(username == '' or password == ''):
			return render_template('register.html', msg = 'Please Enter the Required Fields.')
			
		sql = "select username from users where username='"+username+"'"
		cursor.execute(sql)
		if cursor.rowcount == 1:
			return render_template('register.html', msg = 'Username Already Exists.' )
		
		## Change the values below to change quota values: 1024 is 1MB. Type 1 is Paid Users
		if (type == '1'):
			quota = str(20480.0)
			files = str(35)
			maxfilesize = str(2048.0)
		else:
			quota = str(10240.0)
			files = str(20)
			maxfilesize = str(1024.0)

		sql = "insert into users (username, password, type, initial_quota, quota, files, maxfilesize) values ('"+username+"','"+hashlib.md5(password).hexdigest()+"',"+type+","+quota+","+quota+","+files+","+maxfilesize+")"
		cursor.execute(sql)
		db.commit()
		cursor.close()
		return render_template('login.html')
	else:
		return render_template('register.html', msg = '')
		
		
@app.route('/login', methods=['POST','GET'])
def login():
	if 'username' in session:
		return render_template('index.html', username = session['username'])
	
	## If serves the POST request.	
	if request.method == 'POST':
		db = MySQLdb.connect("localhost","root","root","splitwise")
		cursor = db.cursor()
		
		username = request.form['username']
		password = request.form['password']
		
		sql = "select username from users where username = '"+username+"' and password = '"+hashlib.md5(password).hexdigest()+"'"
		cursor.execute(sql)
		if cursor.rowcount == 1:
			results = cursor.fetchall()
			for row in results:
				session['username'] = username
				cursor.close()
				return redirect(url_for('index'))
		else:
			return render_template('login.html', msg = 'Invalid Username and Password.')
	## Else serves the GET request.
	else:
		return render_template('login.html', msg = '')

@app.route('/logout', methods=['POST','GET'])
def logout():
	if 'username' in session:
		session.pop('username', None)
		session['msg'] = 'Logged Out Successfully'
	return redirect(url_for('login'))

@app.route('/index', methods=['POST','GET'])
def index():	
	return render_template('index.html', username = session['username'], msg = '')	

@app.route('/upload', methods=['POST','GET'])
def upload():		
	if request.method == 'POST':			
		
		db = MySQLdb.connect("localhost","root","root","splitwise")
		cursor = db.cursor()
		
		r = redis.StrictRedis(host='localhost', port=6379, db=0)
		
		file = request.files['file']
		subject = request.form['subject']
		priority = request.form['priority']
		
		# Getting System Time Zone:
		from_zone = tz.tzutc()		#tz.gettz('UTC')
		to_zone = tz.tzlocal()		#tz.gettz('US/Central')
		uploadtime = str(datetime.strptime(str(datetime.now()),'%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=from_zone).astimezone(to_zone))
		
		# Splitting Additional Contents from DateTime
		uploadtime, ext = uploadtime.split("+")
		print '\n\nModified Date:\t'+str(uploadtime)+'\n'
		print '\n\nModified Date:\t'+str(ext)+'\n'		
		
		# Hashing File Contents
		file_contents = file.read()
		hash = hashlib.md5(file_contents).hexdigest()
		#version = 1
		#filename, file_extension = os.path.splitext(file.filename)
		filesize = Decimal(round((Decimal(len(file_contents))/Decimal(1024.0)),4))
		
		sql = "select quota, files, maxfilesize from users where username = '"+session['username']+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			quota = Decimal(row[0])
			files = int(row[1])
			maxfilesize = Decimal(row[2])
				
		quota -= Decimal(round((Decimal(len(file_contents))/Decimal(1024.0)),4))
		files -= 1		
		print '\n\nFile Size:\t'+str(maxfilesize)+'\n'
		print 'Uploaded File Size:\t'+str(filesize)+'\n'
		print '\n\nQuota Remaining:\t'+str(quota)
		print '\nFiles Remaining:\t'+str(files)
		
		# Quota or File Greater than Desired.
		if(quota>=0.0 and files>=0):
			
			# Individual File Size Check
			if filesize<=maxfilesize:
				sql = "select name from files where username = '"+session['username']+"' and hash = '"+hash+"'"
				cursor.execute(sql)
				
				if cursor.rowcount > 0:
					return render_template('index.html', username = session['username'], msg = 'File Already Exists.')
							
				sql = "insert into files (username, hash, name, subject, priority, uploadtime, filesize) values ('"+session['username']+"','"+hash+"','"+file.filename+"','"+subject+"','"+priority+"','"+str(uploadtime)+"','"+str(filesize)+"')"
				cursor.execute(sql)
				
				sql = "update users set quota = '"+str(quota)+"', files = '"+str(files)+"' where username = '"+session['username']+"'"
				cursor.execute(sql)
				db.commit()
				cursor.close()
				
				key = session['username']+"_"+hash
				r.set(key,file_contents)
				print '\nRedis Key:\t'+str(key)
				
				return redirect(url_for('list'))
			
			else:
				return render_template('index.html', username = session['username'], msg = 'File Size Exceeded Max File Size Limit')
		
		else:
			return render_template('index.html', username = session['username'], msg = 'Cannot Upload File as Full Storage Capacity Reached. \nQuota: '+quota+'\tFiles: '+files)
			
	else:
		return render_template('index.html', username = session['username'], msg = '')

@app.route('/list', methods=['POST','GET'])
def list():
	if 'username' not in session:
		return redirect(url_for('register'))

	db = MySQLdb.connect("localhost","root","root","splitwise")
	cursor = db.cursor()
		
	r = redis.StrictRedis(host='localhost', port=6379, db=0)	
	
	list = '<br><center><a href="index">Back</a></center><br>'
	list += '<br><center><a href="search">Search</a></center><br>'
	list += '<div><form action="list" method="post"><center>Sort By: <select name=''sorttype'' id=''sorttype''><option value=''0''>Upload Time Oldest-Newest</option><option value=''1''>Upload Time Newest-Oldest</option><option value=''2''>Priority</option><option value=''3''>Subject</option></select>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<input type="submit" value="Sort"><br><br>'
	list += '<table border="1"><col width="150"><col width="250"><col width="150"><col width="135"><th>FileName - FileSize -  Owner</th><th>File</th><th>Priority - UploadTime</th><th>Options</th>'
	
	OrderClause = 'uploadtime, priority desc'
	
	if request.method == 'POST':			
		sorttype = request.form['sorttype']
		
		if (sorttype == '0'):
		   OrderClause = 'uploadtime'
		elif (sorttype == '1'):
		   OrderClause = 'uploadtime desc'
		elif (sorttype == '2'):
			OrderClause = 'priority desc'
		elif (sorttype == '3'):
			OrderClause = 'subject'
		
	sql = "select hash, name, subject, priority, uploadtime, filesize from files where username = '"+session['username']+"' Order by "+OrderClause
		
	cursor.execute(sql)
	results = cursor.fetchall()
	for row in results:
		hash = row[0]
		filename = row[1]
		subject = row[2]
		priority = str(row[3])
		uploadtime = row[4]
		filesize = row[5]
		
		key = session['username']+"_"+hash
		
		fname,fext=os.path.splitext(filename)
		print '\n File Name: '+fname
		print '\n File Extension: '+fext+'\n'
		
		file_contents = r.get(key)
		
		list += '<tr><td> FName: '+filename+'<br> Size: '+filesize+'<br> Owner: '+session['username']+'</td>'
		if (fext == '.jpeg' or fext == '.jpg' or fext == '.gif' or fext == '.png'):
			image = file_contents.encode("base64")
			list += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/><br><br>Subject: "+subject+"</center></td>"
		else:
			list+= "<td><center>"+file_contents+"<br><br>Subject: "+subject+"</center></td>"
		list += '<td> Priority: '+priority+'<br> UploadTime: '+uploadtime+'</td>'
		list += "<td><a href='view?id="+hash+"&u="+session['username']+"'>View</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
		list += "<a href='modify?id="+hash+"&u="+session['username']+"'>Modify</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
		list += "<a href='delete?id="+hash+"&u="+session['username']+"'>Delete</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
		list += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href='download?id="+hash+"&u="+session['username']+"'>Download</a></td></tr>"
			
	list += '</table></center></form></div>'
	cursor.close()
	return '''<html><head><title>Splitwise</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+list+'''</body></html>'''
	
				
@app.route('/search', methods=['POST','GET'])
def search():
	if 'username' not in session:
		return redirect(url_for('register'))
	
	
	db = MySQLdb.connect("localhost","root","root","splitwise")
	cursor = db.cursor()
	
	r = redis.StrictRedis(host='localhost', port=6379, db=0)
	
	list = '<div class="header"><h3 class="text-muted"><center><br>Search By Subject</center></h3></div>'
	list += '<div><form action="" method="post"><center>'
	list += '<div class="header"><h3 class="text-muted"><center><br><a href=''list''>Back</a></center></h3></div>'
	list += '<div><form action="search" method="post"><center>Subject: <input type="text" name="subject">'
	list += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Sort By: <select name=''sorttype'' id=''sorttype''><option value=''0''>Upload Time Oldest-Newest</option><option value=''1''>Upload Time Newest-Oldest</option><option value=''2''>Priority</option><option value=''3''>Subject</option></select>'
	list += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<input type="submit" value="Search"><br><br><br>'
	
	if request.method == 'POST':
		
		sorttype = request.form['sorttype']
		subject = request.form['subject']
		
		list += '<table border="1"><col width="150"><col width="250"><col width="150"><col width="135"><th>FileName - FileSize -  Owner</th><th>File</th><th>Priority - UploadTime</th><th>Options</th>'
		
		if (sorttype == '0'):
		   OrderClause = 'uploadtime'
		elif (sorttype == '1'):
		   OrderClause = 'uploadtime desc'
		elif (sorttype == '2'):
			OrderClause = 'priority desc'
		elif (sorttype == '3'):
			OrderClause = 'subject'
		else:
			OrderClause = 'uploadtime, priority desc'
		
		sql = "select hash, name, priority, uploadtime, filesize from files where username = '"+session['username']+"' and subject = '"+subject+"' Order by "+OrderClause
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			hash = row[0]
			filename = row[1]
			priority = str(row[2])
			uploadtime = row[3]
			filesize = row[4]
						
			key = session['username']+"_"+hash
			
			fname,fext=os.path.splitext(filename)
			print '\n File Name: '+fname
			print '\n File Extension: '+fext+'\n'
			
			file_contents = r.get(key)
			
			list += '<tr><td> FName: '+filename+'<br> Size: '+filesize+'<br> Owner: '+session['username']+'</td>'
			if (fext == '.jpeg' or fext == '.jpg' or fext == '.gif' or fext == '.png'):
				image = file_contents.encode("base64")
				list += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/><br><br>Subject: "+subject+"</center></td>"
			else:
				list+= "<td><center>"+file_contents+"<br><br>Subject: "+subject+"</center></td>"
			list += '<td> Priority: '+priority+'<br> UploadTime: '+uploadtime+'</td>'
			list += "<td><a href='view?id="+hash+"&u="+session['username']+"'>View</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "<a href='modify?id="+hash+"&u="+session['username']+"'>Modify</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "<a href='delete?id="+hash+"&u="+session['username']+"'>Delete</a>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
			list += "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href='download?id="+hash+"&u="+session['username']+"'>Download</a></td></tr>"
		list += "</table>"
	list += '</center></form></div>'
	cursor.close()
		
	return '''<html><head><title>Splitwise</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+list+'''</body></html>'''

@app.route('/modify', methods=['POST','GET'])
def modify():
		
	db = MySQLdb.connect("localhost","root","root","splitwise")
	cursor = db.cursor()
	
	r = redis.StrictRedis(host='localhost', port=6379, db=0)
		
	hash = request.args.get('id')
	username = request.args.get('u')
	
	if request.method == 'POST':
		formusername = request.form['username']
		formhash = request.form['hash']
		formsubject = request.form['subject']
		formpriority = request.form['priority']
		
		if(formsubject != "" and formpriority != ""):
			sql = "update files set subject = '"+formsubject+"' , priority = '"+formpriority+"' where username = '"+formusername+"' and hash = '"+formhash+"'"
			print '\t'+sql
			cursor.execute(sql)
			db.commit()
			return redirect(url_for('modify', id = formhash, u = formusername))
		else:
			return redirect(url_for('modify', id = formhash, u = formusername))
	
	sql = "select hash, name, subject, priority from files where username = '"+username+"' and hash = '"+hash+"'"
	cursor.execute(sql)
	results = cursor.fetchall()
	
	view = '<br><center><a href="list">Back</a></center><br>'
	view += '<table border="1"><col width="200"><col width="325"><col width="100"><th>FileName</th><th>File-Subject</th><th>Priority</th>'
	for row in results:
		hash = row[0]
		filename = row[1]
		subject = row[2]
		priority = str(row[3])
		
		fname,fext=os.path.splitext(filename)
		key = username+"_"+hash
		file_contents = r.get(key)
		
		view += "<tr><td>"+filename+"</td>"
		if (fext == '.jpeg' or fext == '.jpg' or fext == '.gif' or fext == '.png'):
			image = file_contents.encode("base64")
			view += "<td><center><img src='data:image/jpeg;base64,"+image+"' height='200' width='200'/><br><br>Subject: "+subject+"</center></td>"
		else:
			view+= "<td><center>"+file_contents+"<br><br>Subject: "+subject+"</center></td>"
		view += '<td> Priority: '+priority+'</td></tr>'
	view += '</table><br><hr><br>'
	
	view += "<div><form action='modify' method='post'><center>Modify File Details<br><br>Subject: <input type= 'text' name='subject'><br><br>Priority: <input type= 'text' name='priority'><br><br><input type='hidden' name='username' value= '"+username+"'><input type='hidden' name='hash' value= '"+hash+"'><input type='submit' value='Update'></center></form></div>"
	
	cursor.close()
	return '''<html><head><title>Splitwise</title><link rel="stylesheet" href="static/stylesheets/style.css"></head><body>'''+view+'''</body></html>'''
	
@app.route('/delete', methods=['GET'])
def delete():		
	if request.method == 'GET':			
		
		# db = MySQLdb.connect(unix_socket='/cloudsql/{}:{}'.format(CLOUDSQL_PROJECT,CLOUDSQL_INSTANCE),host='173.194.244.167',user='root',passwd='root',db='instagram',port=3306)
		db = MySQLdb.connect("localhost","root","root","splitwise")
		cursor = db.cursor()
		
		r = redis.StrictRedis(host='localhost', port=6379, db=0)
		
		hash = request.args.get('id')
		username = request.args.get('u')
		
		sql = "select filesize from files where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		result = cursor.fetchall()
		for row in result:
			filesize = Decimal(row[0])
		
		sql = "select quota, files from users where username = '"+username+"'"
		cursor.execute(sql)
		result = cursor.fetchall()
		for row in result:
			quota = Decimal(row[0])
			files = int(row[1])
		
				
		sql = "delete from files where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		db.commit()
		
		key = username+"_"+hash
		r.delete(key)
		
		quota += filesize
		files += 1
		
		sql = "update users set quota = '"+str(quota)+"' , files = '"+str(files)+"' where username = '"+username+"'"
		cursor.execute(sql)
		db.commit()
		
		# sql = "delete from comments where owner = '"+username+"' and hash = '"+hash+"'"
		# cursor.execute(sql)
		# db.commit()
		
		cursor.close()
		return redirect(url_for('list'))
			
@app.route('/download', methods=['GET'])
def download():		
	if request.method == 'GET':			
		
		db = MySQLdb.connect("localhost","root","root","splitwise")	
		cursor = db.cursor()
		
		r = redis.StrictRedis(host='localhost', port=6379, db=0)
		
		hash = request.args.get('id')
		username = request.args.get('u')
		
		sql = "select name from files where username = '"+username+"' and hash = '"+hash+"'"
		cursor.execute(sql)
		results = cursor.fetchall()
		for row in results:
			name = row[0]
			key = username+"_"+hash
			file_contents = r.get(key)
			
		response = make_response(file_contents)
		response.headers["Content-Disposition"] = "attachment; filename="+name
		
		cursor.close()
		return response
			
if __name__ == '__main__':
	app.run(debug=True)
	
	