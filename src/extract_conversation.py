import os
import json
import sys

# usage: python extract_conversation.py <conversation_id> [output_path]

# データのパスをmain.pyと同じにする
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
export_path = os.path.join(base_dir, 'chatgpt_export')
conversations_file = os.path.join(export_path, 'conversations.json')

def extract_conversation(conversation_id, output_path=None):
    if not os.path.exists(conversations_file):
        print(f"conversations.jsonが見つかりません: {conversations_file}")
        return
    with open(conversations_file, 'r', encoding='utf-8') as f:
        conversations = json.load(f)
    for conv in conversations:
        if conv.get('id') == conversation_id:
            if not output_path:
                output_path = os.path.join(export_path, f'conversation_{conversation_id}.json')
            with open(output_path, 'w', encoding='utf-8') as out:
                json.dump(conv, out, ensure_ascii=False, indent=2)
            print(f"抽出完了: {output_path}")
            return
    print(f"該当IDの会話が見つかりません: {conversation_id}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使い方: python extract_conversation.py <conversation_id> [output_path]")
        sys.exit(1)
    conversation_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    extract_conversation(conversation_id, output_path)