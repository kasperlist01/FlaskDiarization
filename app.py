import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from src.task_manager.manager import TaskManager
from src.aggregator.aggregator import TranscriberAggregator
from src.db_service.models import TaskStatus
import threading
app = Flask(__name__)

# Создаем директорию для загрузок, если она не существует
UPLOAD_FOLDER = 'uploads'
SUMMARY_FOLDER = 'summaries'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(SUMMARY_FOLDER, exist_ok=True)

# Инициализируем менеджер задач и агрегатор
task_manager = TaskManager(upload_dir=UPLOAD_FOLDER)
aggregator = TranscriberAggregator()

# Словарь для хранения задач и их статусов
tasks = {}


@app.route('/')
def index():
    """Home page route"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Создаем задачу транскрибации
    task_id = task_manager.create_task(file, options={
        'batch_size': 16,
        'language': request.form.get('language', None)
    })

    thread = threading.Thread(target=aggregator.process_task, args=(task_id,))
    thread.daemon = True
    thread.start()
    return redirect(url_for('view_summary', task_id=task_id))


@app.route('/summary/<task_id>')
def view_summary(task_id):
    """Display the summary results"""
    # Получаем информацию о задаче
    task = task_manager.get_task(task_id)

    if not task:
        return render_template('404.html', message="Task not found"), 404

    # Проверяем статус задачи
    status = task.get('status')

    if status == TaskStatus.COMPLETED.value:
        # Получаем финальный отчет
        task_info = task_manager.get_full_task_info(task_id)
        final_report = task_info.get('summary', {})

        summary = {
            'filename': os.path.basename(task.get('file_path', 'Unknown file')),
            'content': final_report.get('summary', 'No summary available'),
            'task_id': task_id,
            'status': status
        }
        return render_template('summary.html', summary=summary)

    elif status == TaskStatus.FAILED.value:
        summary = {
            'filename': os.path.basename(task.get('file_path', 'Unknown file')),
            'content': 'Processing failed. Please try again.',
            'task_id': task_id,
            'status': status
        }
        return render_template('summary.html', summary=summary)

    else:
        # Задача еще выполняется, показываем страницу ожидания
        summary = {
            'filename': os.path.basename(task.get('file_path', 'Unknown file')),
            'content': 'Your file is being processed. This may take a few minutes...',
            'task_id': task_id,
            'status': status
        }
        return render_template('summary.html', summary=summary, processing=True)


@app.route('/api/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """API endpoint to check task status"""
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify({
        'task_id': task_id,
        'status': task.get('status'),
        'updated_at': task.get('updated_at')
    })


@app.route('/api/summary/<task_id>', methods=['GET'])
def get_summary(task_id):
    """API endpoint to get summary data in JSON format"""
    task = task_manager.get_task(task_id)

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    task_info = task_manager.get_full_task_info(task_id)
    final_report = task_info.get('summary', {})

    summary = {
        'filename': os.path.basename(task.get('file_path', 'Unknown file')),
        'content': final_report.get('summary', 'No summary available'),
        'status': task.get('status'),
        'timestamp': task.get('updated_at')
    }

    # Если запрошен текстовый формат, возвращаем текстовый файл
    if request.args.get('format') == 'text':
        summary_path = os.path.join(SUMMARY_FOLDER, f"{task_id}.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary['content'])
        return send_file(summary_path, as_attachment=True,
                         download_name=f"summary_{os.path.basename(task.get('file_path', 'audio'))}.txt")

    return jsonify(summary)


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('404.html'), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)