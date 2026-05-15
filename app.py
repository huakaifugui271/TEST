# -*- coding: utf-8 -*-
"""
华为云智能旅行手账应用
Flask Web应用主程序
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECRET_KEY, UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH
from utils import (
    extract_image_info,
    format_location_info,
    analyze_travel_image,
    generate_xiaohongshu_journal,
    generate_travel_hashtags,
    format_journal_output
)

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename: str) -> bool:
    """
    检查文件是否为允许的类型
    
    Args:
        filename: 文件名
        
    Returns:
        是否允许
    """
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """
    上传图片并生成旅行手账
    """
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'error': '没有上传文件'}), 400
    
    file = request.files['file']
    
    # 检查文件名
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify({'error': '不支持的文件类型'}), 400
    
    try:
        # 保存文件
        filename = secure_filename(file.filename)
        # 添加时间戳避免重名
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 处理图片并生成手账
        result = process_image(filepath)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'}), 500


def process_image(image_path: str) -> dict:
    """
    处理图片，生成旅行手账
    
    Args:
        image_path: 图片路径
        
    Returns:
        处理结果字典
    """
    result = {
        'success': False,
        'image_path': image_path,
        'journal': None,
        'location': None,
        'datetime': None,
        'image_analysis': None,
        'error': None
    }
    
    try:
        # 1. 提取图片EXIF信息
        image_info = extract_image_info(image_path)
        
        # ========== 调试代码：打印image_info内容 ==========
        print("=" * 50)
        print(f"[调试] image_info = {image_info}")
        print(f"[调试] has_gps = {image_info.get('has_gps')}")
        print(f"[调试] latitude = {image_info.get('latitude')}")
        print(f"[调试] longitude = {image_info.get('longitude')}")
        print(f"[调试] datetime = {image_info.get('datetime')}")
        print("=" * 50)
        # ========== 调试代码结束 ==========
        
        # 2. 获取位置信息
        location_info = None
        if image_info['has_gps']:
            location_info = format_location_info(
                image_info['latitude'],
                image_info['longitude']
            )
        
        # 3. 分析图片内容
        vision_result = analyze_travel_image(image_path)
        image_analysis = vision_result.get('analysis', '无法分析图片内容')
        
        # 4. 生成小红书风格文案
        if location_info:
            journal = generate_xiaohongshu_journal(
                image_analysis,
                location_info,
                image_info.get('datetime')
            )
        else:
            # 没有位置信息时，只根据图片内容生成
            journal = generate_xiaohongshu_journal(
                image_analysis,
                {'address': {'success': False}, 'attractions': []},
                image_info.get('datetime')
            )
        
        # 5. 生成话题标签
        hashtags = generate_travel_hashtags(
            location_info if location_info else {'address': {}, 'attractions': []},
            image_analysis
        )
        
        # 6. 格式化最终输出
        final_journal = format_journal_output(journal, hashtags)
        
        # 构建返回结果
        result['success'] = True
        result['journal'] = final_journal
        result['image_analysis'] = image_analysis
        result['datetime'] = image_info.get('datetime')
        
        if location_info:
            result['location'] = {
                'address': location_info.get('address', {}).get('formatted_address'),
                'city': location_info.get('address', {}).get('city'),
                'attractions': [
                    {
                        'name': attr.get('name'),
                        'distance': attr.get('distance')
                    }
                    for attr in location_info.get('attractions', [])[:3]
                ]
            }
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


@app.route('/preview/<filename>')
def preview_image(filename):
    """预览图片"""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)