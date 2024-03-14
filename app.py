import logging
from uuid import uuid4
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for

import json, os


app = Flask(__name__)

bucket_name = os.getenv('BUCKET_NAME', 'sharegpt-dataset-builder')

def clean_entry(entry):
    entry = entry.strip().replace("\r", "").replace(" \n", "\n")
    return entry


def upload_to_s3(obj, bucket, object_name):
    try:
        import boto3

        s3 = boto3.client('s3')
        s3.put_object(Body=json.dumps(obj), Bucket=bucket, Key=object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True

@app.before_first_request
def before_first_request():
    # store json file in s3 bucket
    import boto3

    s3 = boto3.client('s3')
    bucket_name = 'sharegpt-dataset-builder'

    # if bucket does not exist, create it
    try:
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            s3.create_bucket(Bucket=bucket_name)
        else:
            raise e



# Route for index/main page
@app.route('/', defaults={'active_tab': 'sft'})
@app.route('/<active_tab>')
def index(active_tab):
    return render_template('index.html', active_tab=active_tab)

# Route for the SFT Dataset Builder.
@app.route('/sft', methods=['GET', 'POST'])
def form():
    if request.method == 'POST':
        # Extract form data
        system_prompt = request.form.get('system')
        user_prompts = request.form.getlist('user[]')
        gpt_responses = request.form.getlist('gpt[]')

        # Clean the system prompt, user prompts, and gpt responses
        system_prompt = clean_entry(system_prompt)
        user_prompts = [clean_entry(prompt) for prompt in user_prompts]
        gpt_responses = [clean_entry(response) for response in gpt_responses]
        
        # Data to be appended
        data_to_append = {
            'conversations': [
                {
                    'from': 'system',
                    'value': system_prompt
                }
            ],
            'source': 'manual'
        }

        # Add turns to the conversation
        for user_prompt, gpt_response in zip(user_prompts, gpt_responses):
            data_to_append['conversations'].append({
                'from': 'human',
                'value': user_prompt
            })
            data_to_append['conversations'].append({
                'from': 'gpt',
                'value': gpt_response
            })

        upload_to_s3(data_to_append, bucket_name, 'sft_data_' + str(uuid4()) + '.json')

        return redirect(url_for('index'))
    return redirect(url_for('index'))

# Route for the DPO dataset builder
@app.route('/dpo', methods=['GET', 'POST'])
def dpo_form():
    if request.method == 'POST':
        # Extract form data
        system_prompt = request.form.get('system')
        prompt = request.form.get('prompt')
        chosen = request.form.get('chosen')
        rejected = request.form.get('rejected')

        # Data to be appended
        data_to_append = {
            'system': clean_entry(system_prompt),
            'question': clean_entry(prompt),
            'chosen': clean_entry(chosen),
            'rejected': clean_entry(rejected),
            'source': 'manual'
        }

        upload_to_s3(data_to_append, bucket_name, 'dpo_data_' + str(uuid4()) + '.json')

        return "Success", 200
    return render_template('index.html', active_tab='dpo')

if __name__ == '__main__':
    app.run()