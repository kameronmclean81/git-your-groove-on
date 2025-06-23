from flask import Flask, render_template, request
from TriArbDemo import run_arbitrage

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        result = run_arbitrage()
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
