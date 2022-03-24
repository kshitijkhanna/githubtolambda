import time
import os
import logging
import urllib
import slack
from slack import WebClient
import boto3
import json
import base64
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key, Attr
from urllib.parse import parse_qsl
from base64 import b64decode
import base64
import calendar
import boto3
from botocore.exceptions import ClientError
import requests
from datetime import datetime

 #decrypting bot token
session = boto3.session.Session()
kms = session.client('kms')
encrypted_password = os.environ['BOT_TOKEN']
binary_data = base64.b64decode(encrypted_password)
meta = kms.decrypt(CiphertextBlob=binary_data)
plaintext = meta[u'Plaintext']
bot_token = plaintext.decode()
#print("Bot_token=",bot_token)
sc = slack.WebClient(token = bot_token)


#decrypting  enterprise id
session = boto3.session.Session()
kms = session.client('kms')
encrypted_password_ent_id = os.environ['ent_id']
binary_data_1 = base64.b64decode(encrypted_password_ent_id)
meta = kms.decrypt(CiphertextBlob=binary_data_1)
plaintext1 = meta[u'Plaintext']
ent_id = plaintext1.decode()



# APIs
conv_members_api = 'https://slack.com/api/conversations.members'
useInfo_api = 'https://slack.com/api/users.info'
channelname_api = 'https://slack.com/api/conversations.list'
createdirect_conv = 'https://slack.com/api/conversations.open'
chat_post_api = "https://slack.com/api/chat.postMessage"
chat_post_eph = "https://slack.com/api/chat.postEphemeral"
conv_history_api = 'https://slack.com/api/conversations.history'
views_open = "https://slack.com/api/views.open"

blocks =  [
    {
    	"type": "section",
    	"text": {
    		"type": "mrkdwn",
    		"text": "Webhook already exist for this channel. Would you like to create a new one?"
    	}
    },
    {
    	"type": "actions",
    	"elements": [
    		{
    			"type": "button",
    			"text": {
    				"type": "plain_text",
    				"text": "Yes"
    			}
    		},
    		{
    			"type": "button",
    			"text": {
    				"type": "plain_text",
    				"text": "No"
    			}
    		}
    	]
    }
]

Helpblock = [
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": ":wave: Hello,This app helps to create the webhhook using a simple slash command `/hook` without the need to create a slack app."
			}
		}
]


def posttoslack(channel,blocks):
    res = sc.api_call("chat.postMessage",data={'channel':channel,'blocks':blocks})
    #print(res)	

def send_to_slack_2(channel,text,user):
    sc.api_call(
        "https://slack.com/api/chat.postEphemeral",
        data={'channel':channel,'text': text,'user':user})
        
        
# Parse Input
def parse_input(data):
    parsed = parse_qsl(data, keep_blank_values=True)
    result = {}
    for item in parsed:
        result[item[0]] = item[1]
    return result


def lambda_handler(event, context):
    print(event)
    try:
        #decrypting ver token
        print("decrypting ver token")
        session = boto3.session.Session()
        kms = session.client('kms')
        encrypted_password = os.environ['verification_token']
        #print("encrypted_password",encrypted_password)
        binary_data = base64.b64decode(encrypted_password)
        meta = kms.decrypt(CiphertextBlob=binary_data)
        plaintext = meta[u'Plaintext']
        #print("plaintext",plaintext)
        ver_token = plaintext.decode()
        request_data = parse_input(event["body"])
        #print('request_data=',request_data)
        is_token_valid = request_data['token'] == ver_token
        print('is_token_valid',is_token_valid)
        is_ent_id_valid = request_data['enterprise_id'] == ent_id
        print('is_ent_id_valid',is_ent_id_valid)

        #checking if ENT ID and verification token matches or not
        if not(is_token_valid == True and is_ent_id_valid == True):
            print("Unautorized Access")
            return "401 Unautorized"
            
        elif(is_token_valid == True and is_ent_id_valid == True):   
            try:
                # Checking if the app is added to channnel
                sc.api_call(conv_history_api, data={'channel':request_data['channel_id'],'limit':5})
            except slack.errors.SlackApiError as e:
                if e.response["error"] == 'not_in_channel' or e.response["error"] == 'channel_not_found':
                    response_text = [
                                {
                                    "type": "section",
                                    "block_id": "Invite",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": "Autohook is currently not part to this channel. Please invite the app by typing  @Autohook in the channnel first and then run the command `/hook` again."
                                    }
                                },
                            ]
    
                    response = {"response_type": "ephemeral", 'text': '', 'blocks':response_text}
    
                    return {
                        "body": json.dumps(response),
                        "headers": {"Content-Type": "application/json"},
                        "statusCode": 200,
                           }
            #getting Channel ID from request and comparing it with channelID Field in Dynamodb  
            UserId1 = request_data['user_id']
            channel_id = request_data['channel_id']
            dynamodb = boto3.resource('dynamodb')
            channel_name = request_data['channel_name']               
            table = dynamodb.Table('webhookstore_prod')
            fe = Key('channelID').eq(channel_id)
            response = table.scan(FilterExpression=fe)
            channels= response['Items']
            print(channels)
            if(len(channels)>=0 and request_data['text']=='help'):
                text = "Hello, this app will create an incoming webhook for your channel when you use `/hook` slash command. Read <https://api.slack.com/messaging/webhooks|This article> for more information on Slack Incoming Webhooks."
                send_to_slack_2(channel_id,text,UserId1)
                #posttoslack(channel_id,text,UserId1)
                return {
                'statusCode':200,
                'headers':{},
                'body':''
                }
            elif(len(channels)==0 and request_data['text']==''):
                #print("Channel doesn't exist. Creating webhook")
                private_info = '{"ch_id":'+'"'+request_data['channel_id']+'"'+',"ch_nam":'+'"'+request_data['channel_name']+'"'+',"trigger_id":'+'"'+request_data['trigger_id']+'"'+',"user_id":'+'"'+request_data['user_id']+'"'+',"user_name":'+'"'+request_data['user_name']+'"'+',"team_id":'+'"'+request_data['team_id']+'"'+'}'
                sc.views_open(
                    trigger_id=request_data['trigger_id'],
                    view= {
                        "type": "modal",
                        "private_metadata":private_info,
                        "title": {"type": "plain_text", "text": "Autohook"},
                        "close": {"type": "plain_text", "text": "Cancel"},
                        "blocks": [
                                    {
                            			"type": "section",
                            			"text": {
                            				"type": "mrkdwn",
                            				"text": "`Note` : *PII/PCI* data are not allowed to be posted to Slack."
                            			}
                            		},
                            		{
                            			"type": "divider"
                            		},
                            		{
                            			"type": "section",
                            			"text": {
                            				"type": "mrkdwn",
                            				"text": "*Please acknowledge that the webhook requests would not be used to process or transmit any PII/PCI data*."
                            			},
                            			"accessory": {
                            				"type": "button",
                            				"text": {
                            					"type": "plain_text",
                            					"text": "Acknowledge",
                            					"emoji": True
                            				},
                            				"value": "acknowledge",
                            				"action_id": "acknowledge-button"
                            			}
                            		},
                            		{
                            			"type": "divider"
                            		},
                            		{
                            			"type": "section",
                            			"text": {
                            				"type": "mrkdwn",
                            				"text": "If you need any assistance, please raise your request in `#ask-slack`."
                            			}
                            		}
                    	]
                    	}
                )
                return {
                'statusCode':200,
                'headers':{},
                'body':''
                } 
            #Else channel exists and send the webhook link found from dyamodb
            elif(len(channels)>=1 and request_data['text']==''):
                #text = "Webhook already exist for this channel.Number of webhooks %s.Do you still want to create a new one?" % len(channels)
                posttoslack(channel_id,blocks)
                return {
                    'statusCode': 200,
                    'body': ''
                    #'body': json.dumps(text)
                } 
            

    except:
        print("Some Error Occured")
            