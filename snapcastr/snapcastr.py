import asyncio

from flask import Flask, render_template, redirect, request
from flask_bootstrap import Bootstrap
from flask_nav import Nav
from flask_nav.elements import Navbar, View

import snapcast.control

from wtforms import Form
from wtforms.fields import HiddenField, SelectField, TextField
from wtforms.fields.html5 import IntegerRangeField

navbar = Navbar('snapcastr',
                View('Home', 'index'),
                View('Clients', 'clients'),
                View('Groups', 'groups'),
                View('Streams', 'streams'),
                View('Zones', 'zones')
                )
nav = Nav()
nav.register_element('top', navbar)

app = Flask(__name__)
nav.init_app(app)
Bootstrap(app)


def run_test(loop):
    return (yield from snapcast.control.create_server(loop, start_server.addr, reconnect=True))


def start_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    snapserver = loop.run_until_complete(run_test(loop))
    return [loop, snapserver]


start_server.addr = 'localhost'


class volumeSliderForm(Form):
    hf = HiddenField()
    name = TextField(label='name')
    slider = IntegerRangeField(label='volume')


class streamSelectForm(Form):
    hf = HiddenField()
    name = TextField(label='name')
    clients = TextField(label='clients')
    select = SelectField(label='streams')


class assignForm(Form):
    hf = HiddenField()
    select = SelectField(label='groups')


@app.route('/')
def index():
    loop, snapserver = start_server()
    version = snapserver.version
    num_clients = len(snapserver.clients)
    num_groups = len(snapserver.groups)
    num_streams = len(snapserver.streams)

    return render_template('index.html', version=version, num_clients=num_clients,
                           num_groups=num_groups, num_streams=num_streams)


@app.route('/clients', methods=['GET', 'POST'])
def clients():
    loop, snapserver = start_server()

    if request.method == 'POST':
        data = request.form.to_dict(flat=False)
        for hf, slider in zip(data['hf'], data['slider']):
            client = snapserver.client(hf)
            gg = client.set_volume(int(slider))
            loop.run_until_complete(gg)

    forms = []
    for client in snapserver.clients:
        form = volumeSliderForm(csrf_enabled=False)
        form.slider.default = client.volume
        form.process()
        form.hf.data = client.identifier
        if client.friendly_name:
            form.name.data = client.friendly_name
        else:
            form.name.data = client.identifier
        form.connected = client.connected
        forms.append(form)

    return render_template('clients.html', page='clients', forms=forms)

@app.route('/groups', methods=['GET', 'POST'])
def groups():
    loop, snapserver = start_server()

    if request.method == 'POST':
        data = request.form.to_dict(flat=False)

        for gid, sid in zip(data['hf'], data['select']):
            grp = snapserver.group(gid)

            if sid == '0':
                gg = grp.set_muted(True)
            elif grp.muted:
                gg = grp.set_muted(False)
            else:
                gg = grp.set_stream(sid)

            loop.run_until_complete(gg)

    forms = []
    clients = {client.identifier: client for client in snapserver.clients}
    for group in snapserver.groups:
        form = streamSelectForm(csrf_enabled=False)
        form.select.choices = [
            (
                stream.identifier,
                (stream.friendly_name if stream.friendly_name else stream.identifier) +
                " : " + stream.status
            )
            for stream in snapserver.streams
        ]
        form.select.choices.append(("0", "Mute"))
        form.select.default = "0" if group.muted else group.stream
        form.process()
        if group.friendly_name:
            form.name.data = group.friendly_name
        else:
            form.name.data = group.identifier
        form.clients = [
            client.friendly_name if client.friendly_name else client.identifier
            for client in [clients[client] for client in group.clients]
        ]
        form.hf.data = group.identifier
        forms.append(form)

    return render_template('groups.html', page='groups', forms=forms)

@app.route('/streams')
def streams():
    loop, snapserver = start_server()

    return render_template('streams.html', page='streams', streams=snapserver.streams)

@app.route('/zones', methods=['GET', 'POST'])
def zones():
    loop, snapserver = start_server()

    if request.method == 'POST':
        data = request.form.to_dict(flat=False)
        for cid, gid in zip(data['hf'], data['select']):
            gg = snapserver.group(gid).add_client(cid)
            loop.run_until_complete(gg)

    forms = []
    for client in snapserver.clients:
        form = assignForm(csrf_enabled=False)
        form.select.choices = [
            (
                group.identifier,
                group.friendly_name if group.friendly_name else group.identifier
            )
            for group in snapserver.groups
        ]
        form.select.default = client.group.identifier
        form.process()
        if client.friendly_name:
            form.hf.data = client.friendly_name
        else:
            form.hf.data = client.identifier
        forms.append(form)

    return render_template('zones.html', page='zones', forms=forms)
