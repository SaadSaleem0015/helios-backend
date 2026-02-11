import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pytz
import httpx
import asyncio
# from models.assign_language import AssignedLanguage
from models.user import User


load_dotenv()



vapi_api_key = os.environ["VAPI_API_KEY"]
vapi_org_id = os.environ["VAPI_ORG_ID"]

def generate_token():
    return vapi_api_key

# async def admin_add_payload(assistant_data):
#     print(assistant_data)
#     to_return = {
#         "transcriber": {
#             "provider": assistant_data.transcribe_provider,
#             "model": assistant_data.transcribe_model,
#             "language": assistant_data.transcribe_language,
#             "fallbackPlan": {
#       "transcribers": [
#         {
#           "model": "flux-general-en",
#           "language": "en",
#           "numerals": False,
#           "provider": "deepgram",
#           "confidenceThreshold": 0.4
#         }
#       ]
#     }
#         },
#         "model": {
#             "messages": [
#                 {
#                     "content": assistant_data.systemPrompt,
#                     "role": "system"
#                 }
#             ],
#             "provider": assistant_data.provider,
#             "model": assistant_data.model,
#             "temperature": assistant_data.temperature,
#             "knowledgeBase": {
#                 "provider": "canonical",
#                 "topK": 5,
#                 "fileIds": assistant_data.knowledgeBase
#             },
#             "maxTokens": assistant_data.maxTokens,
#         },
#         "voice": {
#             "provider": assistant_data.voice_provider,
#             "voiceId": assistant_data.voice, 
#         },
#         "firstMessageMode": "assistant-speaks-first",
#         "hipaaEnabled": assistant_data.hipaaEnabled if hasattr(assistant_data, 'hipaaEnabled') else False,
#         "clientMessages": assistant_data.clientMessages,
#         "serverMessages": assistant_data.serverMessages,
#         "silenceTimeoutSeconds": 30,
#         "maxDurationSeconds": assistant_data.maxDurationSeconds if hasattr(assistant_data, 'maxDurationSeconds') else 600,
#         "backgroundSound": "office",
#         "backchannelingEnabled": False,
#         "backgroundDenoisingEnabled": False,
#         "modelOutputInMessagesEnabled": False,
#         "transportConfigurations": [
#             {
#                 "provider": "twilio",
#                 "timeout": 60,
#                 "record": False,
#                 "recordingChannels": "mono"
#             }
#         ],
#         "name": assistant_data.name,
#         "firstMessage": assistant_data.first_message, 
#         "voicemailMessage": assistant_data.voicemailMessage if hasattr(assistant_data, 'voicemailMessage') else "",
#         "endCallMessage": assistant_data.endCallMessage if hasattr(assistant_data, 'endCallMessage') else "",
#         "endCallPhrases": assistant_data.endCallPhrases,
#         "metadata": {},
       
#         "artifactPlan": {
#             "recordingEnabled": assistant_data.audioRecordingEnabled if hasattr(assistant_data, 'audioRecordingEnabled') else True,
#             "videoRecordingEnabled": assistant_data.videoRecordingEnabled if hasattr(assistant_data, 'videoRecordingEnabled') else False,
#             "recordingPath": "<string>"
#         },
#         "messagePlan": {
#             "idleMessages": assistant_data.idleMessages if hasattr(assistant_data, 'idleMessages') else [""],
#             "idleMessageMaxSpokenCount": assistant_data.idleMessageMaxSpokenCount if hasattr(assistant_data, 'idleMessageMaxSpokenCount') else 5,
#             "idleTimeoutSeconds": assistant_data.idleTimeoutSeconds if hasattr(assistant_data, 'idleTimeoutSeconds') else 17.5
#         },
#         "startSpeakingPlan": {
#             "waitSeconds": 0.4,
#             "smartEndpointingEnabled": False,
#             "transcriptionEndpointingPlan": {
#                 "onPunctuationSeconds": 0.1,
#                 "onNoPunctuationSeconds": 1.5,
#                 "onNumberSeconds": 0.5
#             }
#         },
#         "stopSpeakingPlan": {
#             "numWords": 0,
#             "voiceSeconds": 0.2,
#             "backoffSeconds": 1
#         },
#         "monitorPlan": {
#             "listenEnabled": False,
#             "controlEnabled": False
#         },
#     #       "voicemailDetection": {
#     #     "provider": "vapi",
#     #     "backoffPlan": {
#     #     "maxRetries": 5,
#     #     "startAtSeconds": 2,
#     #     "frequencySeconds": 2.5
#     #     },
#     #     "beepMaxAwaitSeconds": 12
#     # },
#     }

#     end_call_tool = {
#         "type": "endCall",
#         "messages": [
#             {
#                 "type": "request-complete",
#                 "content": "Voicemail detected. Ending call immediately."
#             }
#         ]
#     }

#     if (assistant_data.forwardingPhoneNumber):
        
#         to_return["model"]["tools"] = [
#             {
#                 "type": "transferCall",
#                 "destinations": [
#                     {
#                         "type": "number",
#                         "number": assistant_data.forwardingPhoneNumber,
#                         "description": "Transfer to customer support",
#                     }
#                 ]
#             },
#             end_call_tool
#         ]
        
#         to_return["forwardingPhoneNumber"] = assistant_data.forwardingPhoneNumber
#     else:
#         to_return["model"]["tools"] = [end_call_tool]

#     if assistant_data.knowledgeBase and len(assistant_data.knowledgeBase) > 0:
#         tool_response = await create_query_tool(assistant_data.knowledgeBase)
        
#         if tool_response is None:
#             print("Error: Tool creation failed.")
#         else:
#             tool_id = tool_response.get("id") 
            
#             if not tool_id:
#                 to_return["model"]["toolIds"] = []
#             else:
#                 to_return["model"]["toolIds"] = [tool_id]
#                 print(f"Tool ID: {tool_id}")
#     else:
#         print("No knowledgeBase provided or it's empty. Skipping tool creation.")
#         to_return["model"]["toolIds"] = []

#     return to_return



async def user_add_payload(assistant_data,user):
    user = await User.filter(id=user.id).first()


    systemprompt = assistant_data.systemPrompt
    if assistant_data.voice_provider == "deepgram":
        voice_model = "aura"
    else:
        voice_model = "eleven_flash_v2_5"
        
        
    user_payload = {
        "transcriber": {
            "provider": assistant_data.transcribe_provider,
            "model": assistant_data.transcribe_model,
            "language": assistant_data.transcribe_language,
            "fallbackPlan": {
      "transcribers": [
        {
          "model": "flux-general-en",
          "language": "en",
          "numerals": False,
          "provider": "deepgram",
          "confidenceThreshold": 0.4
        }
      ]
    }
        },
        "model": {
            "messages": [
                {
                    "content": systemprompt,
                    "role": "system"
                }
            ],
            "provider": assistant_data.provider,
            "model": assistant_data.model,
            "toolIds": [
            "ac2e8e85-b306-4db0-ba1d-c077858a81f0",
            "9f3da0d0-2d32-495d-bac5-06c505f8d8e7"
            ],
            "temperature": assistant_data.temperature,
            "knowledgeBase": {
                "provider": "canonical",
                "topK": 5,
                "fileIds": assistant_data.knowledgeBase
            },
            "maxTokens": assistant_data.maxTokens,
        },
        "voice": {
            "provider": assistant_data.voice_provider,
            "voiceId": assistant_data.voice,
            "model":voice_model,
        },
        "name": assistant_data.name,
        "firstMessage": assistant_data.first_message,
        "endCallPhrases": assistant_data.endCallPhrases,
            "hooks": [
            {
            "do": [
                {
                "type": "say",
                "exact": "I didn’t hear anything. Are you still there?"
                }
            ],
            "on": "customer.speech.timeout",
            "options": {
                "timeoutSeconds": 10,
                "triggerMaxCount": 1,
                "triggerResetMode": "onUserSpeech"
            }
            
            },
            {
            "on": "customer.speech.timeout",
            "options": {
                "timeoutSeconds": 18,
                "triggerMaxCount": 1,
                "triggerResetMode": "onUserSpeech"
            },
            "do": [
                {
                "type": "say",
                "exact": "I will be ending the call now. Please feel free to call back if you need help.... ... ... Thank you for calling."

                },
                {
                "type": "tool",
                "tool": {
                    "type": "endCall"
                }
                }
            ],
            },
             {
      "on": "customer.speech.interrupted",
      "do": [
        {
          "type": "say",
          "exact": "I apologize for interrupting. Please continue."
        }
      ]
    }
        ],

#           "voicemailDetection": {
#     "provider": "vapi",
#     "backoffPlan": {
#       "maxRetries": 5,
#       "startAtSeconds": 2,
#       "frequencySeconds": 2.5
#     },
#     "beepMaxAwaitSeconds": 12
#   },
    }

    # end_call_tool = {
    #     "type": "endCall",
    #     "messages": [
    #         {
    #             "type": "request-complete",
    #             "content": "Voicemail detected. Ending call immediately."
    #         }
    #     ]
    # }

    if assistant_data.forwardingPhoneNumber:
        user_payload["forwardingPhoneNumber"] = assistant_data.forwardingPhoneNumber
        
        user_payload["model"]["tools"] = [
            {
                "type": "transferCall",
                "destinations": [
                    {
                        "type": "number",
                        "number": assistant_data.forwardingPhoneNumber,
                        "description": "Transfer to customer support",
                    }
                ]
            },
            # end_call_tool
        ]
    # else:
    #     user_payload["model"]["tools"] = [end_call_tool]

    # if assistant_data.knowledgeBase and len(assistant_data.knowledgeBase) > 0:
    #     tool_response = await create_query_tool(assistant_data.knowledgeBase)
        
    #     if tool_response is None:
    #         print("Error: Tool creation failed.")
    #     else:
    #         tool_id = tool_response.get("id") 
            
    #         if not tool_id:
    #             user_payload["model"]["toolIds"] = []
    #         else:
    #             user_payload["model"]["toolIds"] = [tool_id]
    #             print(f"Tool ID: {tool_id}")
    # else:
    #     print("No knowledgeBase provided or it's empty. Skipping tool creation.")
    #     user_payload["model"]["toolIds"] = []
    
    print(user_payload)
    return user_payload


async def create_query_tool(file_ids, tool_name="Query-Tool"):
    url = "https://api.vapi.ai/tool/"
    headers = {
        "Authorization": f"Bearer {vapi_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "type": "query",
        "function": {"name": tool_name},
        "knowledgeBases": [
            {
                "provider": "google",
                "name": "product-kb",
                "description": "Use this knowledge base when the user asks or queries about the product or services",
                "fileIds": file_ids
            }
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code in [200, 201]:
                return response.json() 
            else:
                return None

    except httpx.RequestError as e:
        print(f"An error occurred while requesting the tool creation: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


data = {
    "user@example.com": {
        "username": "user@example.com",
        "full_name": "User Example",
        "email": "user@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    }
}


def get_headers():
    token = generate_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    return headers

def get_file_headers():
    token = generate_token()
    headers = {
        "Authorization": f"Bearer {token}",
    }
    return headers


async def assistant_payload(assistant_data):
    
    # assigned_languages = await AssignedLanguage.filter(company_id=company_id).first()

    # if assigned_languages and assigned_languages.language:
    
    #     if isinstance(assigned_languages.language, list):
    #         languages = ", ".join(assigned_languages.language)
    #     else:
    #         languages = assigned_languages.language
        
    #     systemprompt = f"{assistant_data.systemPrompt} Please note, you can only communicate in the : **{languages}** languages. Any other language will not be understood, and responses will be given only in these languages. If you detect a voicemail or answering machine, immediately end the call using the endCall function."
    # else:
    systemprompt = f"{assistant_data.systemPrompt}"

    
    if assistant_data.voice_provider == "deepgram":
        voice_model = "aura"
    else:
        voice_model = "eleven_flash_v2_5"
        
        
    user_payload = {
        "transcriber": {
            

            "provider": assistant_data.transcribe_provider,
            "model": assistant_data.transcribe_model,
            "language": assistant_data.transcribe_language,
            "fallbackPlan": {
      "transcribers": [
        {
          "model": "flux-general-en",
          "language": "en",
          "numerals": False,
          "provider": "deepgram",
          "confidenceThreshold": 0.4
        }
      ]
    },
        },
        "model": {
            "messages": [
                {
                    "content": systemprompt,
                    "role": "system"
                }
            ],
              "toolIds": [
            "ac2e8e85-b306-4db0-ba1d-c077858a81f0",
            "9f3da0d0-2d32-495d-bac5-06c505f8d8e7"
            ],
            "provider": assistant_data.provider,
            "model": assistant_data.model,
            "temperature": assistant_data.temperature,
            "knowledgeBase": {
                "provider": "canonical",
                "topK": 5,
                "fileIds": assistant_data.knowledgeBase
            },
            "maxTokens": assistant_data.maxTokens,
        },
        "voice": {
            "provider": assistant_data.voice_provider,
            "voiceId": assistant_data.voice,
            "model":voice_model,
        },
        "name": assistant_data.name,
        "firstMessage": assistant_data.first_message,
        "endCallPhrases": assistant_data.endCallPhrases,
            "hooks": [
            {
            "do": [
                {
                "type": "say",
                "exact": "I didn’t hear anything. Are you still there?"
                }
            ],
            "on": "customer.speech.timeout",
            "options": {
                "timeoutSeconds": 10,
                "triggerMaxCount": 1,
                "triggerResetMode": "onUserSpeech"
            }
            
            },
            {
            "on": "customer.speech.timeout",
            "options": {
                "timeoutSeconds": 18,
                "triggerMaxCount": 1,
                "triggerResetMode": "onUserSpeech"
            },
            "do": [
                {
                "type": "say",
                "exact": "I will be ending the call now. Please feel free to call back if you need help.... ... ... Thank you for calling."

                },
                {
                "type": "tool",
                "tool": {
                    "type": "endCall"
                }
                }
            ],
            },
             {
      "on": "customer.speech.interrupted",
      "do": [
        {
          "type": "say",
          "exact": "I apologize for interrupting. Please continue."
        }
      ]
    }
        ],

#         "analysisPlan": {
#             "summaryPrompt": assistant_data.systemPrompt,
#         },
#           "voicemailDetection": {
#     "provider": "vapi",
#     "backoffPlan": {
#       "maxRetries": 5,
#       "startAtSeconds": 2,
#       "frequencySeconds": 2.5
#     },
#     "beepMaxAwaitSeconds": 12
#   },
            }

    # end_call_tool = {
    #     "type": "endCall",
    #     "messages": [
    #         {
    #             "type": "request-complete",
    #             "content": "Voicemail detected. Ending call immediately."
    #         }
    #     ]
    # }

    if assistant_data.forwardingPhoneNumber:
        user_payload["forwardingPhoneNumber"] = assistant_data.forwardingPhoneNumber
        
        user_payload["model"]["tools"] = [
            {
                "type": "transferCall",
                "destinations": [
                    {
                        "type": "number",
                        "number": assistant_data.forwardingPhoneNumber,
                        "description": "Transfer to customer support",
                    }
                ]
            },
            # end_call_tool
        ]
    # else:
    #     user_payload["model"]["tools"] = [end_call_tool]

    # if assistant_data.knowledgeBase and len(assistant_data.knowledgeBase) > 0:
    #     tool_response = await create_query_tool(assistant_data.knowledgeBase)
        
    #     if tool_response is None:
    #         print("Error: Tool creation failed.")
    #     else:
    #         tool_id = tool_response.get("id") 
            
    #         if not tool_id:
    #             user_payload["model"]["toolIds"] = []
    #         else:
    #             user_payload["model"]["toolIds"] = [tool_id]
    #             print(f"Tool ID: {tool_id}")
    # else:
    #     print("No knowledgeBase provided or it's empty. Skipping tool creation.")
    #     user_payload["model"]["toolIds"] = []
    
    print(user_payload)
    return user_payload