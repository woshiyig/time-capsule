import streamlit as st
import hashlib
import json
import os

AUTH_FILE = ".auth_config.json"

def hash_password(password):
    """对密码进行 SHA-256 加密"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_auth_config():
    """加载认证配置"""
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as f:
            return json.load(f)
    return None

def save_auth_config(password):
    """保存初始认证配置"""
    config = {"password_hash": hash_password(password)}
    with open(AUTH_FILE, "w") as f:
        json.dump(config, f)

def check_password():
    """验证用户登录状态"""
    
    # 1. 检查会话状态
    if st.session_state.get("authenticated"):
        return True

    # 2. 检查凭证文件是否存在（首次运行）
    config = load_auth_config()
    
    # 3. 渲染登录页
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            text-align: center;
        }
        .stButton>button {
            width: 100%;
            border-radius: 10px;
            background: #4F8BF9;
            color: white;
            border: none;
            padding: 10px;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background: #3a6ecf;
            box-shadow: 0 4px 12px rgba(79, 139, 249, 0.4);
        }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.title("💊 时间胶囊")
        st.caption("数据已加密保护，请输入访问密码")
        
        if config is None:
            # 首次启动：设置密码
            st.info("检测到首次启动，请设置您的管理员密码")
            new_pwd = st.text_input("设置密码", type="password", key="setup_pwd")
            confirm_pwd = st.text_input("确认密码", type="password", key="confirm_pwd")
            
            if st.button("完成设置"):
                if new_pwd and new_pwd == confirm_pwd:
                    save_auth_config(new_pwd)
                    st.success("密码设置成功！请重新输入登录。")
                    st.rerun()
                elif new_pwd != confirm_pwd:
                    st.error("两次输入的密码不一致")
                else:
                    st.error("密码不能为空")
        else:
            # 正常登录
            password = st.text_input("访问密码", type="password", key="login_pwd")
            if st.button("登录"):
                if hash_password(password) == config["password_hash"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("密码错误，请重试")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    return False

def logout():
    """注销登录"""
    if st.sidebar.button("🔓 注销"):
        st.session_state.authenticated = False
        st.rerun()
