import streamlit as st
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import json
import requests
import time
from datetime import datetime
import zoneinfo
import requests
import warnings # 모든 경고 메시지를 무시합니다.



warnings.filterwarnings("ignore")
DEBUG_MODE = False

st.title("🤖 스포츠 날씨 도우미")

load_dotenv()

# 2. Azure OpenAI 클라이언트 설정
# (실제 값은 .env 파일이나 여기에 직접 입력하세요)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
    
)
weather_api_key = os.getenv("WEATHER_API_KEY")
WEATHER_DATA = {}

# Simplified timezone data
TIMEZONE_DATA = {}

def get_current_weather(location):
    """Get the current weather for a given location"""
    location_lower = location.lower()
    print(f"get_current_weather called with location: {location}")  
    api_key = weather_api_key
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
    data = requests.get(url).json()
    temp = data["main"]["temp"]
    description = data["weather"][0]["description"]
    
    WEATHER_DATA[location_lower] = {
        "raw" : data,
        "location" : location,
        "temp" : temp,
        "desc" : description
        }
    
    for key in WEATHER_DATA:
        if key in location_lower:
            print(f"Weather data found for {key}")  
            weather = WEATHER_DATA[key]
            return json.dumps({
                "location": location,
                "temperature": weather["temp"],
                "desc" : weather["desc"]
            })
    
    print(f"No weather data found for {location_lower}")  
    return json.dumps({"location": location, "temperature": "unknown"})
  

def get_current_time(location):
    """Get the current time for a given location"""
    if DEBUG_MODE == True :
        print(f"get_current_time called with location: {location}")  
    location_lower = location.lower()
    location_cap = location.capitalize()
    
    
    tzlist = [tz for tz in zoneinfo.available_timezones()if f"{location_cap}" in tz]
    if len(tzlist) == 0 :
        print("검색 결과가 없습니다.")
        
    TIMEZONE_DATA[f"{location_lower}"] = tzlist[0]
    
    print(TIMEZONE_DATA)
        
        
    
      
    for key, timezone in TIMEZONE_DATA.items():
        if key in location_lower:
            if DEBUG_MODE == True :
                print(f"Timezone found for {key}")  
            current_time = datetime.now(zoneinfo.ZoneInfo(timezone)).strftime("%I:%M %p")
            return json.dumps({
                "location": location,
                "current_time": current_time
            })
    
    print(f"No timezone data found for {location_lower}")  
    return json.dumps({"location": location, "current_time": "unknown"})


# 3. 대화기록(Session State) 초기화 - 이게 없으면 새로고침 때마다 대화가 날아갑니다!
if "messages" not in st.session_state:
    st.session_state.messages = []
    
# 함수 와 어시스턴트 호출


if "assistant_id" not in st.session_state:
   assistant =  client.beta.assistants.create(
    model="gpt-4o-mini", # replace with model deployment name.
    instructions="당신은 스포츠 도우미입니다. 도시를 물어보면 날씨와 현재 시간을 알려주고, 결과적으로 운동하기 좋은지를 알려주세요. 도시는 영어로 검색하되 답변은 한국어로 하세요.",

  
    tools = [
         {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name, e.g. San Francisco",
                        },
                        
                    },
                    "required": ["location"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current time in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city name, e.g. San Francisco",
                        },
                    },
                    "required": ["location"],
                },
            }
        },
        {"type":"code_interpreter"}
       
    ],
  tool_resources={},
  temperature=1,
  top_p=1
  )
   
   st.session_state.assistant_id = assistant.id
 # Thread 생성 (대화방 1개)
if "thread_id" not in st.session_state:
    st.session_state.thread_id = client.beta.threads.create().id
    
    
# 4. 화면에 기존 대화 내용 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. 사용자 입력 받기
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    # (1) 사용자 메시지 화면에 표시 & 저장
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt
    )

    # (2) AI 응답 생성 (스트리밍 방식 아님, 단순 호출 예시)
    with st.chat_message("assistant"):
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=st.session_state.assistant_id,
        )
        while True:
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread_id,
                run_id=run.id
            )

            if run.status == "completed":
                break

            elif run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                outputs = []

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)

                    if function_name == "get_current_weather":
                       result = get_current_weather(**args)

                       outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                        })
                    
                    elif function_name == "get_current_time":
        
                        result = get_current_time(**args)
                        
                        outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                        })
                    else:
                        print("error: function not found")

                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id,
                    tool_outputs=outputs
                )

          
            elif run.status in ['queued', 'in_progress', 'cancelling']:
                 pass
            else:
                print(run.status)
                time.sleep(0.1)
                
        msgs = client.beta.threads.messages.list(
            thread_id=st.session_state.thread_id
        )
        assistant_reply = msgs.data[0].content[0].text.value

        # 화면 표시
        st.markdown(assistant_reply)

    # (3) AI 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt)


