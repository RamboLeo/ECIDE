// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initPage();

    // 加载提交记录
    loadSubmissions();

    // 设置文件选择事件
    document.getElementById('code-file').addEventListener('change', function(e) {
        const fileName = e.target.files[0]?.name || '未选择文件';
        document.getElementById('file-name').textContent = fileName;
    });

    // 设置表单提交事件
    document.getElementById('upload-form').addEventListener('submit', function(e) {
        e.preventDefault();
        submitCode();
    });
});

// 初始化页面
function initPage() {
    // 检查登录状态
    checkLoginStatus();
}

// 检查登录状态
function checkLoginStatus() {
    // 这里可以添加Token验证逻辑
    console.log('检查登录状态...');
}

// 显示加载动画
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

// 隐藏加载动画
function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// 显示通知
function showNotification(message, type = 'success') {
    // 移除现有的通知
    const existingNotification = document.querySelector('.notification');
    if (existingNotification) {
        existingNotification.remove();
    }

    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type} animate__animated animate__fadeInDown`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span>${message}</span>
        </div>
    `;

    // 添加样式
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#48bb78' : '#f56565'};
        color: white;
        padding: 16px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 10px;
        max-width: 400px;
    `;

    // 添加到页面
    document.body.appendChild(notification);

    // 3秒后自动消失
    setTimeout(() => {
        notification.classList.add('animate__fadeOutUp');
        setTimeout(() => notification.remove(), 1000);
    }, 3000);
}

// 提交代码文件
async function submitCode() {
    const form = document.getElementById('upload-form');
    const formData = new FormData();
    const fileInput = document.getElementById('code-file');
    const projectName = document.getElementById('project-name').value;

    if (!fileInput.files[0]) {
        showNotification('请选择要上传的文件', 'error');
        return;
    }

    if (!projectName) {
        showNotification('请输入项目名称', 'error');
        return;
    }

    formData.append('file', fileInput.files[0]);
    formData.append('project_name', projectName);

    try {
        showLoading();

        const response = await fetch('/api/submit', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showNotification('文件提交成功！');
            form.reset();
            document.getElementById('file-name').textContent = '未选择文件';
            loadSubmissions(); // 重新加载提交记录
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        console.error('提交错误:', error);
        showNotification('提交失败，请检查网络连接', 'error');
    } finally {
        hideLoading();
    }
}

// 加载提交记录
async function loadSubmissions() {
    try {
        showLoading();

        const response = await fetch('/api/submissions');
        const data = await response.json();

        if (data.success) {
            renderSubmissionsTable(data.submissions);
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        console.error('加载提交记录错误:', error);
        showNotification('加载失败，请检查网络连接', 'error');
    } finally {
        hideLoading();
    }
}

// 渲染提交记录表格
function renderSubmissionsTable(submissions) {
    const tbody = document.querySelector('#submissions-table tbody');
    tbody.innerHTML = '';

    if (submissions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px;">
                    <i class="fas fa-inbox" style="font-size: 48px; color: #cbd5e0; margin-bottom: 16px;"></i>
                    <p>暂无提交记录</p>
                </td>
            </tr>
        `;
        return;
    }

    submissions.forEach(sub => {
        const row = document.createElement('tr');
        row.className = 'animate__animated animate__fadeIn';

        // 格式化文件大小
        const fileSize = formatFileSize(sub.file_size);

        row.innerHTML = `
            <td>${sub.id}</td>
            <td>${sub.username}</td>
            <td>${sub.project_name}</td>
            <td>${sub.filename}</td>
            <td>${sub.submission_time}</td>
            <td>${fileSize}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn btn-secondary action-btn" onclick="viewCode(${sub.id})" title="查看代码">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-success action-btn" onclick="editCode(${sub.id})" title="编辑代码">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-primary action-btn" onclick="downloadCode(${sub.id})" title="下载文件">
                        <i class="fas fa-download"></i>
                    </button>
                </div>
            </td>
        `;

        tbody.appendChild(row);
    });
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 查看代码
function viewCode(submissionId) {
    // 在新标签页打开代码编辑器
    window.open(`/editor/${submissionId}?mode=view`, '_blank');
}

// 编辑代码
function editCode(submissionId) {
    // 在新标签页打开代码编辑器
    window.open(`/editor/${submissionId}?mode=edit`, '_blank');
}

// 下载代码
async function downloadCode(submissionId) {
    try {
        showLoading();

        // 直接触发下载
        window.location.href = `/api/download/${submissionId}`;

        // 稍等一会儿再隐藏加载动画，确保下载开始
        setTimeout(() => hideLoading(), 1000);
    } catch (error) {
        console.error('下载错误:', error);
        showNotification('下载失败', 'error');
        hideLoading();
    }
}

// 退出登录
async function logout() {
    try {
        showLoading();

        const response = await fetch('/logout');

        if (response.redirected) {
            window.location.href = response.url;
        }
    } catch (error) {
        console.error('退出登录错误:', error);
        hideLoading();
    }
}