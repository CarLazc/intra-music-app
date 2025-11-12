from extensions import db

class User(db.Model):
    id = db.Column(db.String(80), primary_key=True)
    username = db.Column(db.String(120), nullable=False)
    image_url = db.Column(db.String(255))
    product = db.Column(db.String(50))

class Canciones_Escuchadas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    idUsuario = db.Column(db.String(80), db.ForeignKey('user.id'), nullable=False)
    cancion = db.Column(db.String(500))
    duracionSegundos = db.Column(db.Integer, nullable=True)
    artista = db.Column(db.String(500))
    fechaEscucha = db.Column(db.DateTime, nullable=False)