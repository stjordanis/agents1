import yaml
import os
import argparse
import sys
sys.path.append("../../../src/agents")
sys.path.append("../../cfg")
from SOP import SOP
from Agents import Agent
from Environments import Environment
from Memorys import Memory
from gradio_base import Client
from gradio_example import DebateUI



def process(action):
    response = action.response
    send_name = action.name
    send_role = action.role
    parse = f"{send_name}:"
    # 将里面对话的第三人称删了
    # The third person in the dialogue was deleted.
    while parse in response:
        index = response.index(parse) + len(parse)
        response = response[index:]
    if not action.is_user:
        print(f"{send_name}({send_role}):{response}")
    memory = Memory(send_role, send_name, response)
    return memory



def gradio_process(action,current_state):
    response = action.response
    all = ""
    for i,res in enumerate(response):
        all+=res
        state = 10
        if action.is_user:
            state = 30
            print("state:", state)
        elif action.state_begin:
            state = 12
            action.state_begin = False
        elif i>0:
            state = 11
        print("long:", state)
        Client.send_server(str([state, action.name, res, current_state.name]))
        if state == 30:
            """阻塞当前进程，等待接收"""
            print("client:阻塞等待输入")
            data: list = next(Client.receive_server)
            content = ""
            for item in data:
                if item.startswith("<USER>"):
                    content = item.split("<USER>")[1]
                    break
            print(f"client:接收到了`{content}`")
            action.response = content
            break
        else:
            action.response = all

def init(config):
    agents,roles_to_names,names_to_roles = Agent.from_config(config)
    sop = SOP.from_config(config)
    environment = Environment.from_config(config)
    environment.agents = agents
    environment.roles_to_names,environment.names_to_roles = roles_to_names,names_to_roles
    sop.roles_to_names,sop.names_to_roles = roles_to_names,names_to_roles
    for name,agent in agents.items():
        agent.agent_dict["environment"] = environment
    return agents,sop,environment

def run(agents,sop,environment):
    while True:      
        current_state,current_agent= sop.next(environment,agents)
        if sop.finished:
            print("finished!")
            break
        
        user_input = input(f"{current_agent.name}:") if current_agent.is_user else ""
        action = current_agent.step(current_state,environment,user_input)   #component_dict = current_state[self.role[current_node.name]]   current_agent.compile(component_dict) 
        gradio_process(action,current_state)
        memory = process(action)
        environment.update_memory(memory,current_state)
        

def prepare(agents, sop, environment):
    """建立连接+发送数据+等待接收和启动命令"""
    client = Client()
    Client.send_server = client.send_message
    # 这边需要解析一下，到时候传的时候还要在拼起来
    content = sop.states['Affirmative_Task_Allocation_state'].begin_query
    parse_data = DebateUI.extract(content)
    client.send_message(
        {
            "theme": f"{parse_data[0]}",
            "positive": f"{parse_data[1]}",
            "negative": f"{parse_data[2]}",
            "agents_name": DebateUI.convert2list4agentname(sop)[0],
            "only_name":  DebateUI.convert2list4agentname(sop)[1],
            "default_cos_play_id": -1
        }
    )
    client.listening_for_start_()
    """覆盖参数"""
    if Client.cache["cosplay"] is not None:
        agents[Client.cache["cosplay"]].is_user = True
    sop.states['Negative_Task_Allocation_state'] = sop.states['Affirmative_Task_Allocation_state'].begin_query = \
        DebateUI.merge(
            theme=Client.cache["theme"], positive=Client.cache["positive"], negative=Client.cache["negative"],
            origin_content=sop.states['Affirmative_Task_Allocation_state'].begin_query
        )


if __name__ == '__main__':
    GRADIO = True
    parser = argparse.ArgumentParser(description='A demo of chatbot')
    parser.add_argument('--agent', type=str, help='path to SOP json', default="debate.json")
    parser.add_argument('--config', type=str, help='path to config', default="auto_config.yaml")
    args = parser.parse_args()

    with open(args.config, "r") as file:
        config = yaml.safe_load(file)

    for key, value in config.items():
        os.environ[key] = value
    
    agents,sop,environment = init(args.agent)
    
    if GRADIO:
        prepare(agents, sop, environment)

    run(agents,sop,environment)


    for key, value in config.items():
        del os.environ[key]