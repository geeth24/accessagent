"""
Local test for AgentCore integration
Tests the Converse API with code interpreter primitive
"""
import boto3
import json

def test_agentcore():
    print("Testing AgentCore Converse API...")
    
    bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    # Simple test: ask Claude to execute Python code
    request = {
        "modelId": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": "Use the code interpreter to calculate 2+2 and return the result."
                    }
                ]
            }
        ],
        "system": [
            {
                "text": "You are a helpful assistant with code execution capabilities."
            }
        ],
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0.1
        },
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": "codeInterpreter",
                        "description": "Execute Python code",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string",
                                        "description": "Python code to execute"
                                    }
                                },
                                "required": ["code"]
                            }
                        }
                    }
                }
            ]
        }
    }
    
    try:
        print("Calling Converse API...")
        response = bedrock.converse(**request)
        
        print("\n✅ Success!")
        print(f"Stop reason: {response.get('stopReason')}")
        print(f"Usage: {response.get('usage')}")
        
        output = response.get('output', {})
        message = output.get('message', {})
        
        print("\nResponse content:")
        for content in message.get('content', []):
            if content.get('text'):
                print(f"  Text: {content['text'][:200]}...")
            if content.get('toolUse'):
                tool_use = content['toolUse']
                print(f"  Tool: {tool_use['name']}")
                print(f"  Input: {json.dumps(tool_use.get('input', {}), indent=2)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_agentcore()
    exit(0 if success else 1)
