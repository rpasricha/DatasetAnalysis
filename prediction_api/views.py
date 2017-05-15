from flask import Flask, jsonify, request
import datetime
import uuid
import json
import glob
import os
import models

app = Flask(__name__)

def check_files(model_id):
    metadata_exists = os.path.isfile('metadata/' + model_id)
    model_exists = os.path.isfile('models/' + model_id + '.h5')
    return metadata_exists and model_exists

# Retrieve all valid models
@app.route('/models', methods=['GET'])
def get_all_models():
    # Retrieve all metadata files and return relevant statistics (not all)
    target_uuid = request.args.get('target_uuid')
    statistics = {'models': []}

    files = sorted(glob.glob('metadata/*'))
    for filename in files:
        try:
            f = open(filename, 'r')
            model_info = json.load(f)
            f.close()
        except Exception:
            print('Invalid file found: ' + filename)
            continue

        if 'model_id' not in model_info or 'target_uuid' not in model_info:
            print('Invalid file found: ' + filename)
            continue

        if target_uuid is not None and model_info['target_uuid'] != target_uuid:
            continue

        reduced_info = {}
        reduced_info['model_id'] = model_info['model_id']
        reduced_info['target_uuid'] = model_info['target_uuid']

        statistics['models'].append(reduced_info)

    return jsonify(statistics), 200

# Create and train a new model
@app.route('/models', methods=['POST'])
def create_new_model():
    if not request.is_json:
        # Only accept JSON requests
        print('Error: Request must be in JSON format')
        return jsonify({'Error': 'Request must be in JSON format'}), 400

    # Check if valid JSON
    if request.get_json(silent=True) is None:
        print('Error: Invalid JSON request')
        return jsonify({'Error': 'Invalid JSON request'}), 400

    target_uuid = request.get_json().get('target_uuid')
    date_created = int(datetime.datetime.now().timestamp())
    num_hidden_units = request.get_json().get('num_hidden_units')
    num_autoregressive_terms = request.get_json().get('num_autoregressive_terms')
    delay_length = request.get_json().get('delay_length')
    num_output_values = request.get_json().get('num_output_values')

    if target_uuid is None:
        # Target uuid must be specified
        print('Error: target_uuid not specified')
        return jsonify({'Error': 'target_uuid not specified'}), 400

    # Check that target uuid exists
    time_series_files = sorted(glob.glob('data/*'))
    time_series_uuids = [os.path.splitext(os.path.basename(filename))[0]
                            for filename in time_series_files]
    if target_uuid not in time_series_uuids:
        print('Error: target_uuid does not exist')
        return jsonify({'Error': 'target_uuid does not exist'}), 400

    # Set reasonable defaults
    if num_hidden_units is None:
        num_hidden_units = 100
    if num_autoregressive_terms is None:
        num_autoregressive_terms = 10
    if delay_length is None:
        delay_length = 10
    if num_output_values is None:
        num_output_values = 10

    # Create new model_id, checking for uniqueness
    all_model_files = sorted(glob.glob('metadata/*'))
    all_model_ids = [os.path.basename(filename) for filename in all_model_files]

    model_id = uuid.uuid4().hex
    while model_id in all_model_ids:
        print('model_id already exists')
        model_id = uuid.uuid4().hex

    metadata = {}
    metadata['model_id'] = model_id
    metadata['target_uuid'] = target_uuid
    metadata['date_created'] = date_created
    metadata['num_hidden_units'] = num_hidden_units
    metadata['num_autoregressive_terms'] = num_autoregressive_terms
    metadata['delay_length'] = delay_length
    metadata['num_output_values'] = num_output_values

    # Create and train model
    num_examples, num_features = models.train_model(model_id, target_uuid,
        num_hidden_units, num_autoregressive_terms, delay_length,
        num_output_values)

    metadata['num_features'] = num_features
    metadata['num_examples'] = num_examples

    f = open('metadata/' + metadata['model_id'], 'w')
    json.dump(metadata, f)
    f.close()

    return jsonify(metadata), 200

# Get detailed model information
@app.route('/models/<model_id>', methods=['GET'])
def get_model_info(model_id):
    if os.path.isfile('metadata/' + model_id):
        f = open('metadata/' + model_id, 'r')
        model_info = json.load(f)
        f.close()

        return jsonify(model_info), 200
    else:
        return jsonify({'Error': 'Model not found'}), 404

# Delete a particular model
@app.route('/models/<model_id>', methods=['DELETE'])
def delete_model(model_id):
    if os.path.isfile('metadata/' + model_id):
        os.remove('metadata/' + model_id)

    if os.path.isfile('models/' + model_id + '.h5'):
        os.remove('models/' + model_id + '.h5')

    return 'Model deleted successfully', 200

# Get forecast values from a particular model. Number of forecast values depends
# on the number of specified output values in the model.
@app.route('/models/<model_id>/forecast', methods=['GET'])
def get_model_forecast(model_id):
    if not check_files(model_id):
        return jsonify({'Error': 'Metadata or model file not found'}), 404

    f = open('metadata/' + model_id, 'r')
    model_info = json.load(f)
    f.close()

    forecast = models.get_forecast(model_info)
    return jsonify({'forecast': forecast}), 200

# Get anomalies from a particular model. Anomalies are those points in the
# target time series which have the highest prediction errors.
@app.route('/models/<model_id>/anomalies', methods=['GET'])
def get_model_anomalies(model_id):
    if not check_files(model_id):
        return jsonify({'Error': 'Metadata or model file not found'}), 404

    count = request.args.get('count')
    if count is not None:
        try:
            count = int(count)
        except ValueError:
            return jsonify({'Error': 'Could not parse count'}), 400

    f = open('metadata/' + model_id, 'r')
    model_info = json.load(f)
    f.close()

    anomalies_x, anomalies_y = models.get_anomalies(model_info)

    anomalies = list(zip(anomalies_x, anomalies_y))
    anomalies.sort(key=lambda x: abs(x[1]), reverse=True)
    if count is not None:
        anomalies = anomalies[:count]

    anomalies_x = [x[0] for x in anomalies]
    anomalies_y = [x[1] for x in anomalies]

    return jsonify({'time': anomalies_x, 'error': anomalies_y}), 200

# Get features which have the highest correlations with the target series.
@app.route('/models/<model_id>/correlations', methods=['GET'])
def get_highest_correlations(model_id):
    if not check_files(model_id):
        return jsonify({'Error': 'Metadata or model file not found'}), 404

    count = request.args.get('count')
    if count is None:
        count = 20
    else:
        try:
            count = int(count)
        except ValueError:
            return jsonify({'Error': 'Could not parse count'}), 400

    only_timeseries = request.args.get('only_timeseries')
    if only_timeseries is None:
        only_timeseries = False
    else:
        if only_timeseries.lower() not in ['true', 'false']:
            return jsonify({'Error': 'Only true or false accepted for only_timeseries'}), 400
        else:
            only_timeseries = only_timeseries.lower() == 'true'

    f = open('metadata/' + model_id, 'r')
    model_info = json.load(f)
    f.close()

    correlations = models.get_correlations(model_info)
    if only_timeseries:
        # All non-timeseries columns have an underscore in them
        correlations = [x for x in correlations if '_' not in x[0]]

    columns = [x[0] for x in correlations]
    return jsonify({'columns': columns[:count]}), 200

if __name__ == '__main__':
    app.run()
