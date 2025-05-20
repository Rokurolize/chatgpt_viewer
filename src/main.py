import os
import sys
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_paginate import Pagination, get_page_parameter

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chatgpt_viewer_secret_key'
app.config['JSON_AS_ASCII'] = False

# Windows環境でも動作するようにパス処理を修正
# 実行ファイルからの相対パスで設定
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.config['EXPORT_PATH'] = os.path.join(base_dir, 'chatgpt_export')

# データキャッシュ
conversations_cache = None
conversations_list_cache = None
last_load_time = 0
CACHE_TIMEOUT = 300  # 5分キャッシュ

def load_conversations():
    """会話データをロードし、キャッシュする"""
    global conversations_cache, conversations_list_cache, last_load_time
    
    current_time = time.time()
    if conversations_cache is not None and current_time - last_load_time < CACHE_TIMEOUT:
        return conversations_cache, conversations_list_cache
    
    conversations_file = os.path.join(app.config['EXPORT_PATH'], 'conversations.json')
    
    try:
        print(f"Loading conversations from: {conversations_file}")
        print(f"File exists: {os.path.exists(conversations_file)}")
        
        if not os.path.exists(conversations_file):
            print(f"Export path: {app.config['EXPORT_PATH']}")
            print(f"Files in export path: {os.listdir(app.config['EXPORT_PATH']) if os.path.exists(app.config['EXPORT_PATH']) else 'Directory not found'}")
            return [], []
        
        with open(conversations_file, 'r', encoding='utf-8') as f:
            conversations = json.load(f)
        
        # 会話リストを作成（一覧表示用）
        conversations_list = []
        for conv in conversations:
            # 会話の基本情報を抽出
            conversation_info = {
                'id': conv.get('id', ''),
                'title': conv.get('title', '無題の会話'),
                'create_time': conv.get('create_time', 0),
                'update_time': conv.get('update_time', 0),
                'create_time_str': datetime.fromtimestamp(conv.get('create_time', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'update_time_str': datetime.fromtimestamp(conv.get('update_time', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                'message_count': len(conv.get('mapping', {})) if 'mapping' in conv else 0
            }
            conversations_list.append(conversation_info)
        
        # 更新日時の降順でソート
        conversations_list.sort(key=lambda x: x['update_time'], reverse=True)
        
        conversations_cache = conversations
        conversations_list_cache = conversations_list
        last_load_time = current_time
        
        print(f"Loaded {len(conversations)} conversations")
        return conversations, conversations_list
    except Exception as e:
        print(f"Error loading conversations: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def get_conversation_by_id(conversation_id):
    """IDから会話を取得"""
    conversations, _ = load_conversations()
    
    for conv in conversations:
        if conv.get('id') == conversation_id:
            return conv
    
    return None

def build_conversation_messages(conversation):
    """会話のメッセージを再構築"""
    if not conversation or 'mapping' not in conversation:
        return []
    
    mapping = conversation['mapping']
    
    # ルートノードを探す
    root_id = None
    for node_id, node in mapping.items():
        if node.get('parent') is None:
            root_id = node_id
            break
    
    if not root_id:
        return []
    
    # 会話ツリーを再構築
    messages = []
    
    def traverse_conversation(node_id):
        if node_id not in mapping:
            return
        
        node = mapping[node_id]
        
        if node.get('message'):
            message = node['message']
            author_role = message.get('author', {}).get('role', 'unknown')
            content = message.get('content', {})
            content_type = content.get('content_type', 'text')
            content_parts = content.get('parts', []) if content else []
            content_text = content_parts[0] if content_parts else ''
            
            create_time = message.get('create_time', 0)
            create_time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S') if create_time else ''
            
            messages.append({
                'id': message.get('id', ''),
                'role': author_role,
                'content': content_text,
                'content_type': content_type,
                'create_time': create_time,
                'create_time_str': create_time_str
            })
        
        for child_id in node.get('children', []):
            traverse_conversation(child_id)
    
    traverse_conversation(root_id)
    return messages

# タイムスタンプをフォーマットするフィルター
@app.template_filter('timestamp_to_datetime')
def timestamp_to_datetime(timestamp):
    if not timestamp:
        return ''
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/')
def index():
    """会話一覧ページ"""
    _, conversations_list = load_conversations()
    
    # 検索機能
    search_query = request.args.get('q', '').strip().lower()
    if search_query:
        filtered_conversations = [
            conv for conv in conversations_list 
            if search_query in conv['title'].lower()
        ]
    else:
        filtered_conversations = conversations_list
    
    # ページネーション
    page = request.args.get(get_page_parameter(), type=int, default=1)
    per_page = 50
    offset = (page - 1) * per_page
    
    total = len(filtered_conversations)
    pagination_conversations = filtered_conversations[offset:offset + per_page]
    
    pagination = Pagination(
        page=page, 
        per_page=per_page, 
        total=total, 
        css_framework='bootstrap4'
    )
    
    return render_template(
        'index.html', 
        conversations=pagination_conversations,
        pagination=pagination,
        search_query=search_query,
        total_conversations=total
    )

@app.route('/conversation/<conversation_id>')
def view_conversation(conversation_id):
    """会話詳細ページ"""
    conversation = get_conversation_by_id(conversation_id)
    
    if not conversation:
        return redirect(url_for('index'))
    
    messages = build_conversation_messages(conversation)
    
    return render_template(
        'conversation.html',
        conversation=conversation,
        messages=messages,
        title=conversation.get('title', '無題の会話')
    )

@app.route('/api/conversations')
def api_conversations():
    """会話一覧API"""
    _, conversations_list = load_conversations()
    
    # 検索機能
    search_query = request.args.get('q', '').strip().lower()
    if search_query:
        filtered_conversations = [
            conv for conv in conversations_list 
            if search_query in conv['title'].lower()
        ]
    else:
        filtered_conversations = conversations_list
    
    # ページネーション
    page = request.args.get('page', type=int, default=1)
    per_page = request.args.get('per_page', type=int, default=50)
    offset = (page - 1) * per_page
    
    total = len(filtered_conversations)
    pagination_conversations = filtered_conversations[offset:offset + per_page]
    
    return jsonify({
        'conversations': pagination_conversations,
        'total': total,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/conversation/<conversation_id>')
def api_conversation(conversation_id):
    """会話詳細API"""
    conversation = get_conversation_by_id(conversation_id)
    
    if not conversation:
        return jsonify({'error': 'Conversation not found'}), 404
    
    messages = build_conversation_messages(conversation)
    
    return jsonify({
        'conversation': conversation,
        'messages': messages
    })

if __name__ == '__main__':
    # 起動時にパス情報を表示
    print(f"Base directory: {base_dir}")
    print(f"Export path: {app.config['EXPORT_PATH']}")
    print(f"Export path exists: {os.path.exists(app.config['EXPORT_PATH'])}")
    if os.path.exists(app.config['EXPORT_PATH']):
        print(f"Files in export path: {os.listdir(app.config['EXPORT_PATH'])}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
