import datetime
import flask
import googleapiclient.discovery
import oauth2client.client
import os
import pickle
import time

app = flask.Flask(__name__)
app.secret_key = os.urandom(32)

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'credentials' not in flask.session:
        flow = oauth2client.client.OAuth2WebServerFlow(
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
            scope=['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/admin.directory.resource.calendar.readonly'],
            redirect_uri=flask.request.url_root
        )

        code = flask.request.args.get('code')

        if code is None:
            return flask.redirect(flow.step1_get_authorize_url())
        else:
            flask.session['credentials'] = pickle.dumps(flow.step2_exchange(code))
            return flask.redirect(flask.request.url_root)

    credentials = pickle.loads(flask.session['credentials'])
    event_service = googleapiclient.discovery.build('calendar', 'v3', credentials=credentials).events()
    tz_offset = '-04:00' if time.localtime().tm_isdst else '-05:00'

    if flask.request.method == 'POST':
        event_service.insert(calendarId='primary', body={
            'start': {'dateTime': flask.request.form['start'] + tz_offset},
            'end': {'dateTime': flask.request.form['end'] + tz_offset},
            'attendees': [{'email': flask.request.form['id']}]
        }).execute()
        return 'OK', 200
    else:
        resources = list(map(
            lambda x: {'id': x['resourceEmail'], 'title': x['resourceName']},
            googleapiclient.discovery.build('admin', 'directory_v1', credentials=credentials).resources().calendars().list(
                customer='my_customer',
                fields='items(resourceEmail,resourceName)'
            ).execute()['items']
        ))

        events = []
        for resource in resources:
            events += list(map(lambda x: {
                'id': x['id'],
                'resourceId': resource['id'],
                'start': x['start']['dateTime'],
                'end': x['end']['dateTime'],
                'title': x['summary'] if 'summary' in x else ''
            }, event_service.list(
                calendarId=resource['id'],
                orderBy='startTime',
                singleEvents=True,
                timeMin=datetime.date.today().isoformat() + 'T00:00:00' + tz_offset,
                timeMax=(datetime.date.today() + datetime.timedelta(days=1)).isoformat() + 'T00:00:00' + tz_offset,
                fields='items(id,start,end,summary)'
            ).execute()['items']))

        return flask.render_template('index.html', resources=resources, events=events)
