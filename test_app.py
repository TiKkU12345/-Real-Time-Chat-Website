from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '''
    <h1>Flask is Working!</h1>
    <p>If you can see this, Flask is running correctly.</p>
    <p>Next step: Add Socket.IO</p>
    '''

if __name__ == '__main__':
    print("Starting basic Flask app...")
    app.run(debug=True, host='192.168.1.2', port=5000)