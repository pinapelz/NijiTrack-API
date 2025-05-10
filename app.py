from flask import Flask, send_file, jsonify, request
from flask_cors import CORS

from routes import (
    get_subscribers_data ,get_channel_timeseries,
    get_channel_7d, get_channel_milestones, get_channel_diffs,
    get_channel_info, get_group_mappings
)

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    try:
        return send_file("index.html")
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/subscribers")
def route_subscribers():
    return jsonify(get_subscribers_data())

@app.route("/api/subscribers/<channel_name>")
def route_subscriber_history(channel_name):
    return jsonify(get_channel_timeseries(channel_name))

@app.route("/api/subscribers/<channel_name>/7d")
def route_subscriber_7d(channel_name):
    return jsonify(get_channel_7d(channel_name))

@app.route("/api/subscribers/<channel_name>/milestones")
def route_milestones(channel_name):
    milestone_increment = int(request.args.get("q", 10000))
    return jsonify(get_channel_milestones(channel_name, milestone_increment))

@app.route("/api/subscribers/<channel_name>/past_diff")
def route_diffs(channel_name):
    return jsonify(get_channel_diffs(channel_name))

@app.route("/api/channel/<channel_name>")
def route_channel_info(channel_name):
    return jsonify(get_channel_info(channel_name))

@app.route("/api/groups")
def route_groups():
    return jsonify(get_group_mappings())

@app.errorhandler(404)
def not_found(error):
    return jsonify(error=str(error)), 404

if __name__ == "__main__":
    app.run(debug=True)
