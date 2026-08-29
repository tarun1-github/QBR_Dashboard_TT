# V8 LOGIN SECTION
# dashboard.py imports:
# from app.auth import get_user, verify_password, create_password, update_password

def valid_password(p):
    return len(p)>=8 and any(c.isupper() for c in p) and any(c.islower() for c in p) and any(c.isdigit() for c in p)

def render_login():
    st.markdown("""<style>
    [data-testid="stAppViewContainer"]{background:linear-gradient(135deg,#eef6f8,#f8fbfc,#dfeff2)}
    .qspace{height:7vh}.brand{text-align:center;color:#12344d}.brand h1{font-size:34px;font-weight:900;margin:0}.brand p{color:#507080;font-weight:600}
    .loginbox{max-width:470px;margin:auto;padding:28px 38px;border-radius:34px;background:linear-gradient(145deg,#fff,#eaf3f6);box-shadow:18px 18px 38px rgba(15,39,66,.2),-10px -10px 24px #fff}
    div[data-testid="stTextInput"] input{border-radius:999px!important;height:48px!important;padding:0 20px!important}
    .loginbtn button{border-radius:999px!important;height:54px!important;font-size:17px!important;font-weight:900!important;color:#fff!important;background:linear-gradient(135deg,#0b5873,#147b8b,#24a38c)!important;box-shadow:7px 7px 0 rgba(15,39,66,.16),0 12px 25px rgba(15,39,66,.18)!important}
    </style>""",unsafe_allow_html=True)
    st.markdown('<div class="qspace"></div><div class="brand"><h1>QBR Executive Dashboard</h1><p>HCLTech Operations Command Center</p></div>',unsafe_allow_html=True)
    _,mid,_=st.columns([1,2,1])
    with mid:
        mode=st.session_state.get("auth_mode","login")
        if mode=="set":
            alias=st.session_state.get("pending_alias","")
            db=SessionLocal()
            try: u=get_user(db,alias)
            finally: db.close()
            st.markdown("### 🔐 Set Password")
            if not u: st.error("Username not found.")
            else:
                st.info(f"Welcome, {u['DisplayName']}. This is your first login.")
                p1=st.text_input("New Password",type="password",key="set_p1")
                p2=st.text_input("Confirm Password",type="password",key="set_p2")
                st.caption("Minimum 8 characters with uppercase, lowercase and number.")
                if st.button("Set My Password & Continue",use_container_width=True):
                    if not valid_password(p1): st.error("Password must contain 8+ characters, uppercase, lowercase and number.")
                    elif p1!=p2: st.error("Passwords do not match.")
                    else:
                        db=SessionLocal()
                        try:
                            create_password(db,u["UserID"],p1)
                            st.session_state.user=dict(get_user(db,alias)); st.session_state.auth_mode="dashboard"; st.rerun()
                        finally: db.close()
                if st.button("← Back to Login",use_container_width=True): st.session_state.auth_mode="login"; st.rerun()
            return
        if mode=="forgot":
            st.markdown("### 🔑 Forgot Password")
            alias=st.text_input("Username",key="forgot_username",placeholder="")
            if st.button("Submit Reset Request",use_container_width=True):
                db=SessionLocal()
                try:
                    st.info("Reset request recorded. Please contact the QBR Supervisor/Superuser for the approved reset process.") if get_user(db,alias) else st.error("Username not found.")
                finally: db.close()
            if st.button("← Back to Login",use_container_width=True): st.session_state.auth_mode="login"; st.rerun()
            return
        st.markdown('<div class="loginbox"><h3 style="text-align:center;color:#12344d">🔐 Secure Login</h3></div>',unsafe_allow_html=True)
        username=st.text_input("Username",label_visibility="collapsed",placeholder="",key="login_username")
        password=st.text_input("Password",type="password",label_visibility="collapsed",placeholder="",key="login_password")
        st.markdown('<div class="loginbtn">',unsafe_allow_html=True)
        clicked=st.button("🔐  LOGIN",use_container_width=True)
        st.markdown('</div>',unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            if st.button("Set My Password",use_container_width=True):
                if not username.strip(): st.warning("Enter username first.")
                else: st.session_state.pending_alias=username.strip(); st.session_state.auth_mode="set"; st.rerun()
        with c2:
            if st.button("Forgot Password",use_container_width=True): st.session_state.auth_mode="forgot"; st.rerun()
        if clicked:
            if not username.strip(): st.warning("Please enter username.")
            else:
                db=SessionLocal()
                try:
                    u=get_user(db,username)
                    if not u: st.error("Username not found.")
                    elif not u["IsActive"]: st.error("Account is inactive.")
                    elif u["MustSetPassword"] or not u["PasswordHash"]:
                        st.session_state.pending_alias=username.strip(); st.session_state.auth_mode="set"; st.rerun()
                    elif verify_password(password,u["PasswordHash"]):
                        st.session_state.user=dict(u); st.session_state.auth_mode="dashboard"; st.rerun()
                    else: st.error("Incorrect password.")
                finally: db.close()
