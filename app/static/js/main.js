/**
 * RAG Lite - 基础 JavaScript
 * 通用功能和工具函数
 */

// 等待 DOM 加载完成
document.addEventListener('DOMContentLoaded', function() {
    console.log('RAG Lite initialized');
    
    // 初始化所有组件
    initFlashMessages();
});

/**
 * 初始化 Flash 消息自动关闭
 */
function initFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-messages .alert');
    
    flashMessages.forEach(function(alert) {
        // 5秒后自动关闭
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 300);
        }, 5000);
    });
}

/**
 * 通用 API 请求函数
 * @param {string} url - 请求 URL
 * @param {object} options - fetch 选项
 * @returns {Promise} - 响应数据
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    if (mergedOptions.body && typeof mergedOptions.body === 'object') {
        mergedOptions.body = JSON.stringify(mergedOptions.body);
    }
    
    try {
        const response = await fetch(url, mergedOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || data.message || 'Request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

/**
 * 显示通知消息
 * @param {string} message - 消息内容
 * @param {string} type - 消息类型 (success, error, warning, info)
 */
function showNotification(message, type = 'info') {
    const container = document.querySelector('.flash-messages') || createFlashContainer();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(alert);
    
    // 5秒后自动关闭
    setTimeout(function() {
        alert.style.opacity = '0';
        setTimeout(function() {
            alert.remove();
        }, 300);
    }, 5000);
}

/**
 * 创建 Flash 消息容器
 * @returns {HTMLElement} - 容器元素
 */
function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages container';
    
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.parentNode.insertBefore(container, mainContent);
    } else {
        document.body.insertBefore(container, document.body.firstChild);
    }
    
    return container;
}

/**
 * 格式化日期
 * @param {string|Date} date - 日期
 * @param {string} format - 格式 (short, long, datetime)
 * @returns {string} - 格式化后的日期字符串
 */
function formatDate(date, format = 'short') {
    const d = new Date(date);
    
    switch (format) {
        case 'long':
            return d.toLocaleDateString('zh-CN', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        case 'datetime':
            return d.toLocaleString('zh-CN');
        case 'short':
        default:
            return d.toLocaleDateString('zh-CN');
    }
}

/**
 * HTML 转义
 * @param {string} text - 原始文本
 * @returns {string} - 转义后的文本
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} - 防抖后的函数
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 时间限制（毫秒）
 * @returns {Function} - 节流后的函数
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
