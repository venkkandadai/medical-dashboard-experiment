import os
import pandas as pd
import streamlit as st
import altair as alt
import streamlit_authenticator as stauth
import time
import datetime
import json
import uuid
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from io import BytesIO

# Set page config first
st.set_page_config(
    page_title="Wharton Street College of Medicine Dashboard",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADMIN CONFIGURATION ---
# 🔄 IMPORTANT: Add your email address to access analytics
ADMIN_EMAILS = [
    "venkkandadai@gmail.com",  # 🔄 Replace with YOUR email address
    "medschool.dashboard.prototype@gmail.com",
    "kmcallister@nbme.org",    # System email has admin access
    # Add more researcher/admin emails as needed:
    # "researcher2@university.edu",
    # "supervisor@medschool.edu",
]

def is_admin(user_email):
    """Check if user has admin access to analytics"""
    return user_email in ADMIN_EMAILS

# --- ANALYTICS TRACKING FUNCTIONS ---
def initialize_session():
    """Initialize session tracking"""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
        st.session_state["session_start"] = time.time()
        # Log session start
        current_user = st.session_state.get("username")
        if current_user:
            log_user_action(current_user, "session_start", {
                "session_id": st.session_state["session_id"],
                "start_time": st.session_state["session_start"]
            })

def log_session_activity():
    """Log ongoing session activity (called on each page load)"""
    current_user = st.session_state.get("username")
    if current_user and "session_start" in st.session_state:
        current_time = time.time()
        session_duration = current_time - st.session_state["session_start"]
       
        log_user_action(current_user, "session_activity", {
            "session_id": st.session_state["session_id"],
            "session_duration_seconds": round(session_duration, 1),
            "session_duration_minutes": round(session_duration / 60, 2)
        })

def log_user_action(user_email, action, details=None):
    """Log user actions for experiment analytics"""
    if user_email:  # Only log for authenticated users
       
        # Convert pandas/numpy types to native Python types for JSON serialization
        def make_json_serializable(obj):
            """Convert pandas/numpy types to JSON-serializable types"""
            if hasattr(obj, 'item'):  # numpy types
                return obj.item()
            elif hasattr(obj, 'to_pydatetime'):  # pandas datetime
                return obj.to_pydatetime().isoformat()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            else:
                return obj
       
        # Clean the details dictionary
        clean_details = make_json_serializable(details or {})
       
        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "session_id": st.session_state.get("session_id", "unknown"),
            "user_email": user_email,
            "action": action,
            "details": clean_details,
            "page_mode": st.session_state.get("current_mode", "unknown")
        }
       
        # Save to analytics file
        analytics_file = "experiment_analytics.json"
        with open(analytics_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

def log_page_view(user_email, mode):
    """Track page/mode changes"""
    st.session_state["current_mode"] = mode
    log_user_action(user_email, "page_view", {"mode": mode})

def log_student_lookup(user_email, student_id, student_name, exam_filter):
    """Track student lookup behavior"""
    log_user_action(user_email, "student_lookup", {
        "student_id": student_id,
        "student_name": student_name,
        "exam_filter": exam_filter
    })

def log_cohort_analysis(user_email, cohorts, exams):
    """Track cohort analysis behavior"""
    log_user_action(user_email, "cohort_analysis", {
        "selected_cohorts": cohorts,
        "selected_exams": exams,
        "num_cohorts": len(cohorts),
        "num_exams": len(exams)
    })

def log_triage_usage(user_email, cohort, risk_levels, exam_filter, num_students):
    """Track triage feature usage"""
    log_user_action(user_email, "triage_usage", {
        "cohort": cohort,
        "risk_levels": risk_levels,
        "exam_filter": exam_filter,
        "students_found": num_students
    })

def log_feature_interaction(user_email, feature, details):
    """Track specific feature usage"""
    log_user_action(user_email, "feature_interaction", {
        "feature": feature,
        "details": details
    })

def log_user_frustration(user_email, frustration_type, context):
    """Track when users hit dead ends or frustrations"""
    log_user_action(user_email, "user_frustration", {
        "frustration_type": frustration_type,  # "no_data", "search_failed", "error_encountered", "empty_results"
        "context": context,
        "page": st.session_state.get("current_mode", "unknown"),
        "timestamp": datetime.datetime.now().isoformat()
    })

def log_feature_discovery(user_email, feature_name, context):
    """Track when users first discover and use features"""
    # Check if this is the user's first time using this feature
    analytics_file = "experiment_analytics.json"
    is_first_time = True
    
    if os.path.exists(analytics_file):
        try:
            with open(analytics_file, "r") as f:
                for line in f:
                    data = json.loads(line.strip())
                    if (data.get('user_email') == user_email and 
                        data.get('action') == 'feature_discovery' and
                        data.get('details', {}).get('feature_name') == feature_name):
                        is_first_time = False
                        break
        except:
            pass  # If file reading fails, assume first time
    
    log_user_action(user_email, "feature_discovery", {
        "feature_name": feature_name,
        "is_first_time_use": is_first_time,
        "context": context,
        "discovery_timestamp": datetime.datetime.now().isoformat()
    })

def log_workflow_stage(user_email, workflow_type, stage, details=None):
    """Track workflow progression and completion rates"""
    log_user_action(user_email, "workflow_stage", {
        "workflow_type": workflow_type,  # "student_analysis", "cohort_analysis", "triage_workflow"
        "stage": stage,  # "started", "data_viewed", "analysis_completed", "action_taken"
        "stage_timestamp": datetime.datetime.now().isoformat(),
        "session_id": st.session_state.get("session_id", "unknown"),
        "details": details or {}
    })

# --- PDF REPORT GENERATION ---
def generate_student_pdf_report(student_data, student_exams, student_epc, student_qlf, selected_name, selected_id):
    """Generate comprehensive PDF report for advisor meeting prep"""
   
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
   
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
   
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue,
        borderWidth=1,
        borderColor=colors.darkblue,
        borderPadding=5
    )
   
    # Story container for PDF content
    story = []
   
    # Title and Header
    story.append(Paragraph("🩺 Student Performance Report", title_style))
    story.append(Paragraph(f"Academic Advisor Meeting Preparation", styles['Normal']))
    story.append(Spacer(1, 20))
   
    # Student Information Section
    story.append(Paragraph("👤 Student Information", heading_style))
    student_info_data = [
        ["Student Name:", selected_name],
        ["Student ID:", selected_id],
        ["Report Generated:", datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")],
        ["Generated By:", "Wharton Street College of Medicine Dashboard"]
    ]
   
    student_table = Table(student_info_data, colWidths=[2*inch, 4*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 20))
   
    # Performance Summary
    if not student_exams.empty:
        story.append(Paragraph("📊 Performance Summary", heading_style))
       
        # Calculate summary metrics
        latest_exam = student_exams.sort_values("exam_date").iloc[-1]
        avg_score = student_exams["total_score"].mean()
        score_trend = "Improving" if len(student_exams) > 1 and student_exams.sort_values("exam_date").iloc[-1]["total_score"] > student_exams.sort_values("exam_date").iloc[0]["total_score"] else "Stable"
       
        summary_data = [
            ["Total Exams Taken:", str(len(student_exams))],
            ["Most Recent Score:", f"{latest_exam['total_score']} ({get_readiness_status(latest_exam['flag'])})"],
            ["Average Score:", f"{avg_score:.1f}"],
            ["Performance Trend:", score_trend],
        ]
       
        if 'step1_pass_prob' in latest_exam.index and pd.notna(latest_exam['step1_pass_prob']):
            summary_data.append(["Step 1 Pass Probability:", f"{latest_exam['step1_pass_prob']:.1%}"])
       
        summary_table = Table(summary_data, colWidths=[2.5*inch, 3.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
   
    # Exam History
    if not student_exams.empty:
        story.append(Paragraph("📈 Complete Exam History", heading_style))
       
        exam_data = []
        exam_data.append(["Exam Type", "Date", "Score", "Step 1 Readiness", "Performance Band"])
       
        for _, exam in student_exams.sort_values("exam_date").iterrows():
            band = exam.get('band', 'N/A')
            readiness_status = get_readiness_status(exam['flag'])
            exam_data.append([
                exam['exam_type'],
                exam['exam_date'],
                str(exam['total_score']),
                readiness_status,
                band if pd.notna(band) else 'N/A'
            ])
       
        exam_table = Table(exam_data, colWidths=[1.2*inch, 1.2*inch, 0.8*inch, 1.3*inch, 1.5*inch])
        exam_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
       
        # Color code readiness status
        for i, row in enumerate(exam_data[1:], 1):
            # Get original flag for this row to determine color
            original_exam = student_exams.sort_values("exam_date").iloc[i-1]
            flag = original_exam['flag']
            if flag == "Red":
                exam_table.setStyle(TableStyle([('BACKGROUND', (3, i), (3, i), colors.mistyrose)]))
            elif flag == "Yellow":
                exam_table.setStyle(TableStyle([('BACKGROUND', (3, i), (3, i), colors.lightyellow)]))
            elif flag == "Green":
                exam_table.setStyle(TableStyle([('BACKGROUND', (3, i), (3, i), colors.lightgreen)]))
       
        story.append(exam_table)
        story.append(Spacer(1, 20))
   
    # Areas for Improvement - EPC
    if not student_epc.empty:
        story.append(Paragraph("📚 Content Areas Needing Attention (EPC)", heading_style))
       
        epc_long = student_epc.melt(id_vars=["student_id", "exam_type", "exam_date"], var_name="EPC", value_name="Score")
        epc_long["Score"] = pd.to_numeric(epc_long["Score"], errors='coerce')
        epc_long = epc_long.dropna(subset=["Score"]).copy()
       
        if not epc_long.empty:
            weakest_epcs = epc_long.sort_values("Score").head(8)  # Top 8 areas for improvement
           
            epc_data = [["Content Area", "Score", "Recommendation"]]
            for _, row in weakest_epcs.iterrows():
                score = row['Score']
                if score < 50:
                    recommendation = "High Priority - Immediate Focus Needed"
                elif score < 60:
                    recommendation = "Medium Priority - Targeted Review"
                else:
                    recommendation = "Low Priority - Monitor Progress"
               
                epc_data.append([
                    row['EPC'][:40] + "..." if len(row['EPC']) > 40 else row['EPC'],
                    f"{score:.1f}%",
                    recommendation
                ])
           
            epc_table = Table(epc_data, colWidths=[2.5*inch, 1*inch, 2.5*inch])
            epc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(epc_table)
        else:
            story.append(Paragraph("No EPC data available for analysis.", styles['Normal']))
       
        story.append(Spacer(1, 20))
   
    # Areas for Improvement - QLF
    if not student_qlf.empty:
        story.append(Paragraph("🔍 Question-Level Performance (QLF)", heading_style))
       
        student_qlf["correct"] = pd.to_numeric(student_qlf["correct"], errors='coerce')
        student_qlf_clean = student_qlf.dropna(subset=["correct", "score_category"]).copy()
        student_qlf_clean = student_qlf_clean[student_qlf_clean["score_category"].notna()].copy()
       
        if not student_qlf_clean.empty:
            qlf_summary = student_qlf_clean.groupby("score_category")["correct"].agg(["count", "sum"])
            qlf_summary["pct_correct"] = 100 * qlf_summary["sum"] / qlf_summary["count"]
            qlf_summary = qlf_summary.sort_values("pct_correct")
           
            qlf_data = [["Category", "Questions", "Correct", "% Correct", "Focus Area"]]
            for category, row in qlf_summary.iterrows():
                pct = row['pct_correct']
                if pct < 60:
                    focus = "Immediate Review Needed"
                elif pct < 75:
                    focus = "Additional Practice Recommended"
                else:
                    focus = "Continue Current Approach"
               
                qlf_data.append([
                    category,
                    str(int(row['count'])),
                    str(int(row['sum'])),
                    f"{pct:.1f}%",
                    focus
                ])
           
            qlf_table = Table(qlf_data, colWidths=[1.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 1.8*inch])
            qlf_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(qlf_table)
        else:
            story.append(Paragraph("No QLF data available for analysis.", styles['Normal']))
       
        story.append(Spacer(1, 20))
   
    # Advisor Talking Points
    story.append(Paragraph("🎯 Suggested Discussion Points for Advisor Meeting", heading_style))
   
    talking_points = []
   
    # Add performance-based talking points
    if not student_exams.empty:
        latest_exam = student_exams.sort_values("exam_date").iloc[-1]
        readiness_status = get_readiness_status(latest_exam['flag'])
       
        if latest_exam['flag'] == 'Red':
            talking_points.append("• **Immediate Intervention**: Student is below Step 1 readiness threshold - discuss intensive support strategies")
            talking_points.append("• **Step 1 Timing**: Consider additional preparation time before Step 1 attempt")
        elif latest_exam['flag'] == 'Yellow':
            talking_points.append("• **Targeted Support**: Student is approaching readiness - focus on specific content areas to reach Step 1 ready status")
            talking_points.append("• **Progress Monitoring**: Schedule follow-up in 2-3 weeks to track improvement")
        else:
            talking_points.append("• **Maintain Excellence**: Student shows Step 1 readiness - discuss strategies for maintaining consistency")
       
        if 'step1_pass_prob' in latest_exam.index and pd.notna(latest_exam['step1_pass_prob']):
            pass_prob = latest_exam['step1_pass_prob']
            if pass_prob < 0.6:
                talking_points.append(f"• **Step 1 Risk Assessment**: Current pass probability is {pass_prob:.1%} - develop comprehensive remediation plan")
            elif pass_prob < 0.8:
                talking_points.append(f"• **Step 1 Preparation Strategy**: Pass probability is {pass_prob:.1%} - discuss focused preparation approach")
   
    # Add content-specific talking points
    if not student_epc.empty:
        epc_long = student_epc.melt(id_vars=["student_id", "exam_type", "exam_date"], var_name="EPC", value_name="Score")
        epc_long["Score"] = pd.to_numeric(epc_long["Score"], errors='coerce')
        epc_long = epc_long.dropna(subset=["Score"]).copy()
       
        if not epc_long.empty:
            weakest_epc = epc_long.sort_values("Score").iloc[0]
            talking_points.append(f"• **Content Priority**: Focus remediation on {weakest_epc['EPC']} (current performance: {weakest_epc['Score']:.1f}%)")
   
    # Add study strategy recommendations
    talking_points.extend([
        "• **Academic Plan Review**: Evaluate current study schedule and identify optimization opportunities",
        "• **Support Resources**: Discuss tutoring, study groups, or learning specialist consultation",
        "• **Goal Setting**: Establish specific, measurable objectives for next assessment period",
        "• **Wellness Check**: Assess stress management and work-life balance strategies"
    ])
   
    for point in talking_points:
        story.append(Paragraph(point, styles['Normal']))
        story.append(Spacer(1, 6))
   
    story.append(Spacer(1, 20))
   
    # Footer
    story.append(Paragraph("---", styles['Normal']))
    story.append(Paragraph("This report was generated by the Wharton Street College of Medicine Dashboard for academic advisor use.", styles['Italic']))
    story.append(Paragraph(f"Report ID: {uuid.uuid4().hex[:8]}", styles['Italic']))
   
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- EMAIL CONFIGURATION ---
# ⚠️ IMPORTANT: Configure these settings for your email provider
import os

EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",  
    "smtp_port": 587,                
    "sender_email": os.getenv("GMAIL_EMAIL", "medschool.dashboard.prototype@gmail.com"),
    "sender_password": os.getenv("GMAIL_APP_PASSWORD", "vmfh gjlo jhxp xrqk"),
    "sender_name": "Wharton Street College of Medicine Dashboard"
}

def send_reset_email(recipient_email, reset_token, recipient_name):
    """Send password reset email with secure token"""
    try:
        # Create reset link - update this URL when you deploy
        base_url = os.getenv("APP_URL", "https://medical-dashboard-experiment.onrender.com")  # 🔄 Change this to your deployed URL
        reset_link = f"{base_url}/?reset_token={reset_token}"
       
        # Create email content
        subject = "Password Reset Request - Wharton Street College of Medicine Dashboard"
       
        html_body = f"""
        <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello {recipient_name},</p>
                <p>You requested a password reset for your Wharton Street College of Medicine Dashboard account.</p>
                <p><strong>Click the link below to reset your password:</strong></p>
                <p><a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>Or copy and paste this link into your browser:</p>
                <p>{reset_link}</p>
                <p><strong>This link will expire in 1 hour for security.</strong></p>
                <p>If you didn't request this reset, please ignore this email.</p>
                <br>
                <p>Best regards,<br>Wharton Street College of Medicine IT Support</p>
            </body>
        </html>
        """
       
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{EMAIL_CONFIG['sender_name']} <{EMAIL_CONFIG['sender_email']}>"
        msg['To'] = recipient_email
       
        # Add HTML content
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
       
        # Send email
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
       
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def generate_reset_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)

def save_reset_token(email, token):
    """Save reset token with timestamp"""
    token_file = "reset_tokens.csv"
    current_time = time.time()
   
    # Load existing tokens or create new DataFrame
    if os.path.exists(token_file):
        tokens_df = pd.read_csv(token_file)
    else:
        tokens_df = pd.DataFrame(columns=["email", "token", "timestamp"])
   
    # Remove old tokens for this email
    tokens_df = tokens_df[tokens_df["email"] != email]
   
    # Add new token
    new_token = pd.DataFrame([{
        "email": email,
        "token": token,
        "timestamp": current_time
    }])
    tokens_df = pd.concat([tokens_df, new_token], ignore_index=True)
   
    # Clean up expired tokens (older than 1 hour)
    one_hour_ago = current_time - 3600
    tokens_df = tokens_df[tokens_df["timestamp"] > one_hour_ago]
   
    # Save updated tokens
    tokens_df.to_csv(token_file, index=False)

def verify_reset_token(token):
    """Verify if reset token is valid and not expired"""
    token_file = "reset_tokens.csv"
   
    if not os.path.exists(token_file):
        return None
   
    tokens_df = pd.read_csv(token_file)
    current_time = time.time()
    one_hour_ago = current_time - 3600
   
    # Find valid token
    valid_token = tokens_df[
        (tokens_df["token"] == token) &
        (tokens_df["timestamp"] > one_hour_ago)
    ]
   
    if not valid_token.empty:
        return valid_token.iloc[0]["email"]
    return None

def clear_reset_token(token):
    """Remove used reset token"""
    token_file = "reset_tokens.csv"
   
    if os.path.exists(token_file):
        tokens_df = pd.read_csv(token_file)
        tokens_df = tokens_df[tokens_df["token"] != token]
        tokens_df.to_csv(token_file, index=False)

# Initialize session tracking
initialize_session()

# --- AUTHENTICATION SETUP ---
user_db_path = "users.csv"

# Force login or registration
if "authentication_status" not in st.session_state or not st.session_state["authentication_status"]:
    st.sidebar.title("🩺 Wharton Street College of Medicine Dashboard")
    auth_mode = st.sidebar.radio("Account Access", ["Login", "Register", "Reset Password"])
    st.session_state["auth_mode"] = auth_mode
else:
    auth_mode = st.session_state.get("auth_mode", "Login")

# Handle different authentication modes
if auth_mode == "Register":
    st.sidebar.header("Create a New Account")
    new_email = st.sidebar.text_input("Email")
    new_first_name = st.sidebar.text_input("First Name")
    new_last_name = st.sidebar.text_input("Last Name")
    new_title = st.sidebar.text_input("Title/Role (e.g., Academic Advisor, Dean)")
    new_medical_school = st.sidebar.text_input("Institution Name")
    new_password = st.sidebar.text_input("Password", type="password")
    
    # NDA Agreement
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📋 Research Agreement**")
    nda_agreed = st.sidebar.checkbox(
        "I agree to participate in this research prototype and understand that this dashboard is for evaluation purposes only. I agree to provide feedback and not share this prototype outside my institution.",
        key="nda_checkbox"
    )
   
    if st.sidebar.button("Register"):
        if not nda_agreed:
            st.sidebar.error("❌ You must agree to the research terms to register.")
        elif not all([new_email, new_first_name, new_last_name, new_password]):
            st.sidebar.error("❌ Please fill in all required fields.")
        else:
            if os.path.exists(user_db_path):
                users_df = pd.read_csv(user_db_path)
            else:
                users_df = pd.DataFrame(columns=["email", "first_name", "last_name", "name", "title", "medical_school", "password"])

            if new_email in users_df["email"].values:
                st.sidebar.error("❌ Email already registered.")
            else:
                hashed_pw = stauth.Hasher.hash(new_password)
                # Create full name for compatibility with authenticator
                full_name = f"{new_first_name} {new_last_name}".strip()
                users_df = pd.concat([
                    users_df,
                    pd.DataFrame([{
                        "email": new_email,
                        "first_name": new_first_name,
                        "last_name": new_last_name,
                        "name": full_name,  # Keep for authenticator compatibility
                        "title": new_title,
                        "medical_school": new_medical_school,
                        "password": hashed_pw,
                        "nda_agreed": True,
                        "nda_date": datetime.datetime.now().isoformat(),
                        "nda_version": "v1.0"
                    }])
                ], ignore_index=True)
                users_df.to_csv(user_db_path, index=False)
                st.sidebar.success("✅ Account created! Please login.")
        st.stop()

# Check for reset token in URL parameters
query_params = st.query_params
reset_token = query_params.get("reset_token", None)

if reset_token:
    # Handle password reset with token
    st.sidebar.header("🔒 Reset Your Password")
   
    # Verify token
    token_email = verify_reset_token(reset_token)
    if token_email:
        st.sidebar.success("✅ Valid reset link!")
        new_password = st.sidebar.text_input("Enter New Password", type="password", key="new_pwd")
        confirm_password = st.sidebar.text_input("Confirm New Password", type="password", key="confirm_pwd")
       
        if st.sidebar.button("Update Password"):
            if new_password and new_password == confirm_password:
                if len(new_password) >= 6:
                    # Load users and update password
                    if os.path.exists(user_db_path):
                        users_df = pd.read_csv(user_db_path)
                        hashed_pw = stauth.Hasher.hash(new_password)
                        users_df.loc[users_df["email"] == token_email, "password"] = hashed_pw
                        users_df.to_csv(user_db_path, index=False)
                       
                        # Clear the used token
                        clear_reset_token(reset_token)
                       
                        st.sidebar.success("✅ Password updated successfully!")
                        st.sidebar.info("Please log in with your new password.")
                       
                        # Clear URL parameters
                        st.query_params.clear()
                        st.rerun()
                    else:
                        st.sidebar.error("User database not found.")
                else:
                    st.sidebar.error("Password must be at least 6 characters long.")
            else:
                st.sidebar.error("Passwords don't match or are empty.")
    else:
        st.sidebar.error("❌ Invalid or expired reset link.")
        st.sidebar.info("Please request a new password reset.")
   
    st.stop()

if auth_mode == "Reset Password":
    st.sidebar.header("🔑 Request Password Reset")
    st.sidebar.info("Enter your email address and we'll send you a secure reset link.")
   
    reset_email = st.sidebar.text_input("Email Address")
   
    if st.sidebar.button("Send Reset Email"):
        if reset_email:
            # Check if email exists
            if os.path.exists(user_db_path):
                users_df = pd.read_csv(user_db_path)
                if reset_email in users_df["email"].values:
                    # Generate and save token
                    token = generate_reset_token()
                    save_reset_token(reset_email, token)
                   
                    # Get user name for personalized email
                    user_info = users_df[users_df["email"] == reset_email].iloc[0]
                    user_name = user_info.get("name", user_info.get("first_name", "User"))
                   
                    # Send email (only if EMAIL_CONFIG is properly configured)
                    if EMAIL_CONFIG["sender_email"] != "your-email@gmail.com":
                        if send_reset_email(reset_email, token, user_name):
                            st.sidebar.success("✅ Reset email sent! Check your inbox.")
                            st.sidebar.info("The reset link will expire in 1 hour.")
                        else:
                            st.sidebar.error("❌ Failed to send email. Contact administrator.")
                    else:
                        st.sidebar.warning("⚠️ Email not configured. Contact administrator.")
                        st.sidebar.info(f"Admin: Use token {token} for manual reset.")
                else:
                    # Don't reveal if email exists or not (security)
                    st.sidebar.success("✅ If that email exists, a reset link has been sent.")
            else:
                st.sidebar.error("User database not found.")
        else:
            st.sidebar.error("Please enter an email address.")
    st.stop()

# Login logic
if os.path.exists(user_db_path):
    users_df = pd.read_csv(user_db_path)
   
    # Handle legacy user databases that might not have new columns
    required_columns = ["first_name", "last_name", "title", "medical_school", "name", "nda_agreed", "nda_date", "nda_version"]
    for col in required_columns:
        if col not in users_df.columns:
         if col == "nda_agreed":
            users_df[col] = False  # Default to False for boolean
        else:
            users_df[col] = ""     # Default to empty string for others
   
    # Create full name field if it doesn't exist (for authenticator compatibility)
    if users_df["name"].fillna("").eq("").all():
        users_df["name"] = (users_df["first_name"] + " " + users_df["last_name"]).str.strip()
   
    # For legacy users who only have "name" field, try to split into first/last
    missing_names = users_df["first_name"].fillna("") == ""
    if missing_names.any():
        for idx, row in users_df[missing_names].iterrows():
            if pd.notna(row["name"]) and row["name"].strip():
                name_parts = row["name"].strip().split()
                users_df.loc[idx, "first_name"] = name_parts[0] if name_parts else ""
                users_df.loc[idx, "last_name"] = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
else:
    st.error("No users registered yet. Please register first.")
    st.stop()

# Set up authenticator
user_creds = {
    "usernames": {
        row["email"]: {"name": row["name"], "password": row["password"]}
        for _, row in users_df.iterrows()
    }
}

cookie_config = {
    "name": "dashboard_auth",
    "key": "some_secret_key_change_this",
    "expiry_days": 1
}

authenticator = stauth.Authenticate(user_creds, cookie_config["name"], cookie_config["key"], cookie_config["expiry_days"])





# --- COMPLETE WORKING AUTHENTICATION SYSTEM ---

# Handle login
if auth_mode == "Login":
    if not st.session_state.get("authentication_status", False):
        st.sidebar.header("🔐 Login")
        
        with st.sidebar.form("login_form"):
            login_email = st.text_input("Email Address")
            login_password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")
        
        if login_button:
            if login_email and login_password:
                if os.path.exists(user_db_path):
                    users_df = pd.read_csv(user_db_path)
                    
                    if login_email in users_df["email"].values:
                        user_row = users_df[users_df["email"] == login_email].iloc[0]
                        stored_password = user_row["password"]
                        
                        # Use bcrypt to verify password
                        import bcrypt
                        try:
                            # Try bcrypt verification (most common)
                            if bcrypt.checkpw(login_password.encode('utf-8'), stored_password.encode('utf-8')):
                                password_correct = True
                            else:
                                password_correct = False
                        except:
                            # Fallback: check if it's a plain hash we can verify differently
                            test_hash = stauth.Hasher.hash(login_password)
                            password_correct = (test_hash == stored_password)
                        
                        if password_correct:
                            # Login successful
                            st.session_state["authentication_status"] = True
                            st.session_state["username"] = login_email
                            st.session_state["name"] = user_row.get("name", user_row.get("first_name", "User"))
                            
                            # Log successful login
                            log_user_action(login_email, "login_success", {"name": st.session_state["name"]})
                            log_session_activity()
                            
                            st.sidebar.success("✅ Login successful!")
                            st.rerun()
                        else:
                            st.sidebar.error("❌ Invalid password")
                    else:
                        st.sidebar.error("❌ Email not found")
                else:
                    st.sidebar.error("❌ No users found")
            else:
                st.sidebar.error("❌ Please enter both email and password")

# Set authentication status for the rest of the app
authentication_status = st.session_state.get("authentication_status", False)
username = st.session_state.get("username")
name = st.session_state.get("name", "User")

# Handle logout
if authentication_status:
    if st.sidebar.button("🚪 Logout"):
        # Log session end
        current_user = st.session_state.get("username")
        if current_user and "session_start" in st.session_state:
            session_end_time = time.time()
            session_duration = session_end_time - st.session_state["session_start"]
            log_user_action(current_user, "session_end", {
                "session_id": st.session_state["session_id"],
                "session_duration_seconds": round(session_duration, 1),
                "session_duration_minutes": round(session_duration / 60, 2)
            })
        
        # Clear session
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Check authentication before continuing
if not authentication_status:
    st.warning("Please log in to access the dashboard")
    st.info("Use the sidebar to login, register, or reset your password")
    st.stop()

# Helper function to convert internal flags to professional readiness terminology
def get_readiness_status(flag):
    """Convert internal flag values to professional readiness terminology"""
    flag_mapping = {
        "Green": "Step 1 Ready",
        "Yellow": "Approaching Readiness",
        "Red": "Below Readiness Threshold"
    }
    return flag_mapping.get(flag, flag)

def get_readiness_emoji(flag):
    """Get emoji for readiness status"""
    emoji_mapping = {
        "Green": "✅",
        "Yellow": "⚠️",
        "Red": "🚨"
    }
    return emoji_mapping.get(flag, "")

def get_readiness_color_style(flag):
    """Get background color for readiness status"""
    if flag == "Green":
        return "background-color: #d4edda; color: #155724;"
    elif flag == "Yellow":
        return "background-color: #fff3cd; color: #856404;"
    elif flag == "Red":
        return "background-color: #f8d7da; color: #721c24;"
    return ""
@st.cache_data
def load_data():
    base_path = "data"

    students = pd.read_csv(os.path.join(base_path, "students_master.csv"))
    cbse = pd.read_csv(os.path.join(base_path, "cbse_summary.csv"))
    cbssa = pd.read_csv(os.path.join(base_path, "cbssa_summary.csv"))
    qlf = pd.read_csv(os.path.join(base_path, "cbse_qlf.csv"))

    # Initial deduplication
    cbse = cbse.loc[:, ~cbse.columns.duplicated()].copy()
    cbssa = cbssa.loc[:, ~cbssa.columns.duplicated()].copy()

    # Renaming operations - handle the actual date column names from R
    cbse = cbse.rename(columns={
        "cbse_epc_score": "total_score",
        "cbse_date": "exam_date"
    })
   
    # For CBSSA: Use cbssa_date (the actual CBSSA exam date) and drop the original exam_date
    if "cbssa_date" in cbssa.columns:
        cbssa = cbssa.drop(columns=["exam_date"])  # Remove the CBSE date
        cbssa = cbssa.rename(columns={
            "cbssa_epc_score": "total_score",
            "cbssa_date": "exam_date"  # Use the actual CBSSA date
        })
    else:
        # Fallback if structure is different
        cbssa = cbssa.rename(columns={"cbssa_epc_score": "total_score"})

    # Add exam type columns
    cbse["exam_type"] = "CBSE"
    cbssa["exam_type"] = "CBSSA"

    # CRITICAL FIX: Remove duplicates again after renaming operations
    cbse = cbse.loc[:, ~cbse.columns.duplicated()].copy()
    cbssa = cbssa.loc[:, ~cbssa.columns.duplicated()].copy()

    def assign_flag(score):
        if score >= 66:
            return "Green"
        elif score >= 62:
            return "Yellow"
        else:
            return "Red"

    # Apply readiness flags (internal values remain the same for consistency)
    cbse["flag"] = cbse["total_score"].apply(assign_flag)
    cbssa["flag"] = cbssa["total_score"].apply(assign_flag)

    # Define required columns - now including the additional metrics
    cols = ["student_id", "exam_type", "exam_date", "total_score", "flag", "step1_pass_prob"]
   
    # Add exam_round if it exists (needed for proper exam grouping)
    if "exam_round" in cbse.columns:
        cols.append("exam_round")
   
    # Add band columns if they exist
    if "cbse_band" in cbse.columns:
        cols.append("cbse_band")
    if "cbssa_band" in cbssa.columns:
        cbssa_cols = cols.copy()
        if "cbse_band" not in cbssa.columns:
            cbssa_cols = [col for col in cols if col != "cbse_band"]
        cbssa_cols.append("cbssa_band")
    else:
        cbssa_cols = cols.copy()
   
    # Check if all required columns exist before subsetting
    missing_cbse = [col for col in cols if col not in cbse.columns]
    missing_cbssa = [col for col in cbssa_cols if col not in cbssa.columns]
   
    if missing_cbse:
        st.error(f"Missing columns in CBSE data: {missing_cbse}")
        st.write("Available CBSE columns:", list(cbse.columns))
   
    if missing_cbssa:
        st.error(f"Missing columns in CBSSA data: {missing_cbssa}")
        st.write("Available CBSSA columns:", list(cbssa.columns))
   
    # Create subsets with explicit column selection
    cbse_subset = cbse[cols].copy()
    cbssa_subset = cbssa[cbssa_cols].copy()
   
    # Standardize column names for concatenation
    if "cbssa_band" in cbssa_subset.columns:
        cbssa_subset = cbssa_subset.rename(columns={"cbssa_band": "band"})
    if "cbse_band" in cbse_subset.columns:
        cbse_subset = cbse_subset.rename(columns={"cbse_band": "band"})
   
    # Ensure both DataFrames have the same columns
    final_cols = ["student_id", "exam_type", "exam_date", "total_score", "flag", "step1_pass_prob", "band"]
   
    # Add exam_round if it exists in either dataset
    if "exam_round" in cbse_subset.columns or "exam_round" in cbssa_subset.columns:
        final_cols.append("exam_round")
   
    # Add missing columns if needed
    for col in final_cols:
        if col not in cbse_subset.columns:
            cbse_subset[col] = None
        if col not in cbssa_subset.columns:
            cbssa_subset[col] = None
   
    # Reorder columns to match
    cbse_subset = cbse_subset[final_cols]
    cbssa_subset = cbssa_subset[final_cols]
   
    # Additional safety check: ensure no duplicates in subset DataFrames
    cbse_subset = cbse_subset.loc[:, ~cbse_subset.columns.duplicated()].copy()
    cbssa_subset = cbssa_subset.loc[:, ~cbssa_subset.columns.duplicated()].copy()

    # Now concatenate
    try:
        exam_records = pd.concat([cbse_subset, cbssa_subset], ignore_index=True)
    except Exception as e:
        st.error(f"Error during concatenation: {e}")
        st.write("CBSE subset columns:", list(cbse_subset.columns))
        st.write("CBSSA subset columns:", list(cbssa_subset.columns))
        st.write("CBSE subset shape:", cbse_subset.shape)
        st.write("CBSSA subset shape:", cbssa_subset.shape)
        raise

    # EPC processing with duplicate handling
    static_cols = ["student_id", "exam_type", "exam_date"]
   
    # Add exam_round to static columns if it exists (needed for cohort analytics)
    if "exam_round" in cbse.columns or "exam_round" in cbssa.columns:
        static_cols.append("exam_round")
   
    exclude_cols = set(static_cols + [
        "total_score", "flag", "cohort_year", "step1_pass_prob",
        "step1_ready", "in_low_pass_range", "cbse_band", "cbssa_band", "band",
        "exam_order", "month", "year_offset", "exam_year",
        "first_name", "last_name", "full_name"  # Name fields should not be EPC subjects
    ])

    # Get EPC columns, ensuring no duplicates
    epc_cols_cbse = [col for col in cbse.columns if col not in exclude_cols]
    epc_cols_cbssa = [col for col in cbssa.columns if col not in exclude_cols]
    shared_epc_cols = sorted(set(epc_cols_cbse).intersection(epc_cols_cbssa))

    # Create EPC dataframes with duplicate column handling
    cbse_epc_cols = static_cols + shared_epc_cols
    cbssa_epc_cols = static_cols + shared_epc_cols
   
    cbse_epc = cbse[cbse_epc_cols].copy()
    cbssa_epc = cbssa[cbssa_epc_cols].copy()
   
    # Remove any remaining duplicates
    cbse_epc = cbse_epc.loc[:, ~cbse_epc.columns.duplicated()].copy()
    cbssa_epc = cbssa_epc.loc[:, ~cbssa_epc.columns.duplicated()].copy()

    try:
        epc_scores = pd.concat([cbse_epc, cbssa_epc], axis=0, ignore_index=True)
    except Exception as e:
        st.error(f"Error during EPC concatenation: {e}")
        st.write("CBSE EPC columns:", list(cbse_epc.columns))
        st.write("CBSSA EPC columns:", list(cbssa_epc.columns))
        raise

    # QLF processing
    qlf["exam_type"] = "CBSE"
    # Extract score category from detailed content area descriptions
    # Content areas look like: "Diagnosis: Behavioral health: factitious disorders"
    qlf["score_category"] = qlf["content_area"].str.extract(r"^\s*(Diagnosis|Foundation|Gen Principle)", expand=False)
    qlf_responses = qlf.loc[:, ~qlf.columns.duplicated()].copy()

    return students, exam_records, epc_scores, qlf_responses

# Load data with error handling
try:
    students, exam_records, epc_scores, qlf_responses = load_data()
    st.session_state['data_loaded'] = True
    st.session_state['students'] = students
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

# --- CLA DATA LOADING (SEPARATE AND MODULAR) ---
@st.cache_data
def load_cla_data():
    """Load CLA data separately from main dashboard data"""
    try:
        base_path = "data"
        cla_data = pd.read_csv(os.path.join(base_path, "cla_results.csv"))
        
        # Basic data cleaning
        cla_data['correct'] = pd.to_numeric(cla_data['correct'], errors='coerce')
        cla_data['exercise'] = pd.to_numeric(cla_data['exercise'], errors='coerce')
        
        return cla_data
        
    except Exception as e:
        st.error(f"Error loading CLA data: {str(e)}")
        return pd.DataFrame()
    
# --- CLA-SPECIFIC ANALYTICS FUNCTIONS ---
def log_cla_action(user_email, action, details=None):
    """Log CLA-specific user actions separately from main dashboard analytics"""
    if user_email:
        def make_json_serializable(obj):
            if hasattr(obj, 'item'):
                return obj.item()
            elif hasattr(obj, 'to_pydatetime'):
                return obj.to_pydatetime().isoformat()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            else:
                return obj
        
        clean_details = make_json_serializable(details or {})
        
        log_entry = {
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().isoformat(),
            "session_id": st.session_state.get("session_id", "unknown"),
            "user_email": user_email,
            "action": action,
            "details": clean_details,
            "feature_type": "CLA",  # Mark as CLA-specific
            "page_mode": "Communication Skills Analytics"
        }
        
        # Save to separate CLA analytics file
        cla_analytics_file = "cla_experiment_analytics.json"
        with open(cla_analytics_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")



# --- MAIN APPLICATION ---
st.sidebar.title("🩺 Wharton Street College of Medicine Dashboard")

# Show Analytics tab only for admin users
current_user = st.session_state.get("username")
if current_user and is_admin(current_user):
    mode_options = ["Home", "Individual Student Dashboard", "Cohort Analytics", "At-Risk Student Triage", "🗣️ CLA Analytics", "📊 Analytics"]
else:
    mode_options = ["Home", "Individual Student Dashboard", "Cohort Analytics", "At-Risk Student Triage", "🗣️ CLA Analytics"]

page = st.sidebar.selectbox("Navigation", mode_options)

# Log page navigation
if current_user:
    log_page_view(current_user, page)

# --- HOME PAGE ---
if page == "Home":
    st.markdown("# 🩺 Welcome to Wharton Street College of Medicine Dashboard")
    st.markdown("## Medical Student Performance Analytics")
   
    col1, col2 = st.columns([2, 1])
   
    with col1:
        st.markdown("### 🎯 Dashboard Features")
        st.markdown("""
        **📊 Individual Student Dashboard**
        - Complete exam history with performance trends
        - Step 1 pass probability analytics
        - Content area breakdowns (EPC & QLF)
        - Risk flag indicators
       
        **🏥 Cohort Analytics**
        - Multi-cohort performance comparisons
        - Content area heatmaps
        - Longitudinal trend analysis
        - National benchmarking capabilities
       
        **🚨 At-Risk Student Triage**
        - Automated risk identification
        - Priority student lists
        - Export capabilities for interventions
        - Performance band analysis
        """)
   
    with col2:
        st.markdown("### 📈 Quick Stats")
        if 'students' in st.session_state:
            students_data = st.session_state['students']
            st.metric("👥 Total Students", len(students_data))
           
            # Get cohort info
            cohorts = sorted(students_data['cohort_year'].unique())
            st.metric("📚 Cohorts", f"{len(cohorts)} cohorts")
            st.metric("📅 Years", f"{min(cohorts)}-{max(cohorts)}")
       
    # Display user profile information
    if authentication_status and username:
        st.markdown("---")
        user_info = users_df[users_df["email"] == username].iloc[0]
        st.subheader("👤 Your Profile")
        col1, col2 = st.columns(2)
       
        with col1:
            if user_info.get('first_name') and user_info.get('last_name'):
                st.write(f"**Name:** {user_info['first_name']} {user_info['last_name']}")
            elif user_info.get('name'):
                st.write(f"**Name:** {user_info['name']}")
            st.write(f"**Email:** {user_info['email']}")
       
        with col2:
            if user_info.get('title'):
                st.write(f"**Title:** {user_info['title']}")
            if user_info.get('medical_school'):
                st.write(f"**Medical School:** {user_info['medical_school']}")
       
        # Log profile view
        log_feature_interaction(username, "profile_view", {
            "has_title": bool(user_info.get('title')),
            "has_medical_school": bool(user_info.get('medical_school'))
        })
       
        # Admin quick stats (only for admins)
        if is_admin(username):
            st.markdown("---")
            st.subheader("🔧 Admin Quick Stats")
           
            # Load basic analytics for quick view
            analytics_file = "experiment_analytics.json"
            if os.path.exists(analytics_file):
                try:
                    with open(analytics_file, "r") as f:
                        line_count = sum(1 for _ in f)
                   
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        user_count = len(users_df)
                        st.metric("👥 Total Users", user_count)
                    with col2:
                        st.metric("📊 Total Actions", line_count)
                    with col3:
                        st.info("📈 View full analytics in Analytics tab")
                       
                    # Show data status for admin
                    if st.session_state.get('data_loaded', False):
                        students_data = st.session_state['students']
                        st.success(f"✅ Dashboard data: {len(students_data)} students loaded")
                    else:
                        st.warning("⚠️ Dashboard data not loaded")
                       
                except Exception as e:
                    st.info("📊 Analytics data will appear as users interact with the dashboard")
            else:
                st.info("📊 Analytics data will appear as users interact with the dashboard")

# --- INDIVIDUAL STUDENT DASHBOARD ---
elif page == "Individual Student Dashboard":
    st.markdown("# 👤 Individual Student Dashboard")
   
    # --- Student Lookup ---
    st.sidebar.header("Student Filters")
    students["full_name"] = students["last_name"].str.strip() + ", " + students["first_name"].str.strip()
    students = students.sort_values(["full_name", "student_id"])
    student_name_map = dict(zip(students["full_name"], students["student_id"]))
    selected_name = st.sidebar.selectbox("Select Student Name", list(student_name_map.keys()))
    selected_id = student_name_map[selected_name]
    st.sidebar.info(f"Student ID: {selected_id}")

    # Track workflow start
    log_workflow_stage(current_user, "student_analysis", "started", {
    "student_id": selected_id,
    "student_name": selected_name
})

    student_exams = exam_records[exam_records["student_id"] == selected_id].copy()
    student_epc = epc_scores[epc_scores["student_id"] == selected_id].copy()
    student_qlf = qlf_responses[qlf_responses["student_id"] == selected_id].copy()

    exam_ids = student_exams[["exam_type", "exam_date"]].drop_duplicates()
   
    # Create labels using exam_round if available, otherwise use date
    if 'exam_round' in student_exams.columns:
        # Create a temporary merge to get exam_round for labeling
        exam_ids_with_round = student_exams[["exam_type", "exam_date", "exam_round"]].drop_duplicates()
        exam_ids_with_round["label"] = exam_ids_with_round["exam_type"] + " - " + exam_ids_with_round["exam_round"].astype(str).str.replace('MS', 'ME')
        exam_label_map = dict(zip(exam_ids_with_round["label"], zip(exam_ids_with_round["exam_type"], exam_ids_with_round["exam_date"])))
    else:
        # Fallback to date-based labels
        exam_ids["label"] = exam_ids["exam_type"] + " - " + exam_ids["exam_date"]
        exam_label_map = dict(zip(exam_ids["label"], zip(exam_ids["exam_type"], exam_ids["exam_date"])))
   
    exam_ids = exam_ids.sort_values("exam_date")
    selected_exam_label = st.sidebar.selectbox("Select Exam Type and Date", ["All"] + list(exam_label_map.keys()))

    if selected_exam_label != "All":
        selected_exam_type, selected_exam_date = exam_label_map[selected_exam_label]
        student_exams = student_exams[(student_exams["exam_type"] == selected_exam_type) & (student_exams["exam_date"] == selected_exam_date)].copy()
        student_epc = student_epc[(student_epc["exam_type"] == selected_exam_type) & (student_epc["exam_date"] == selected_exam_date)].copy()
        # For QLF, use exam_date (which corresponds to the CBSE exam date)
        student_qlf = student_qlf[student_qlf["exam_date"] == selected_exam_date].copy()

    # Log student lookup
    log_student_lookup(current_user, selected_id, selected_name, selected_exam_label)

    st.markdown(f"### **Student:** {selected_name}  **ID:** {selected_id}")
   
    # PDF Report Generation Button
    st.markdown("---")
    col1, col2 = st.columns(2)
   
    # Get student's first name for personalized button
    student_first_name = students[students["student_id"] == selected_id].iloc[0]['first_name']
   
    with col1:
        if st.button("📄 Generate Meeting Prep Report (PDF)", use_container_width=True):
            with st.spinner("Generating comprehensive report..."):
                try:
                    # Track feature discovery
                    log_feature_discovery(current_user, "pdf_report_generation", "individual_student_dashboard")

                    # Track workflow completion
                    log_workflow_stage(current_user, "student_analysis", "action_taken", {
                        "action_type": "pdf_generated",
                        "student_id": selected_id
                    })

                    # Generate PDF with all student data
                    pdf_buffer = generate_student_pdf_report(
                        student_data=students[students["student_id"] == selected_id].iloc[0],
                        student_exams=exam_records[exam_records["student_id"] == selected_id],
                        student_epc=epc_scores[epc_scores["student_id"] == selected_id],
                        student_qlf=qlf_responses[qlf_responses["student_id"] == selected_id],
                        selected_name=selected_name,
                        selected_id=selected_id
                    )
                   
                    # Log PDF generation with enhanced tracking
                    exam_data = exam_records[exam_records["student_id"] == selected_id]
                    epc_data = epc_scores[epc_scores["student_id"] == selected_id]
                    qlf_data = qlf_responses[qlf_responses["student_id"] == selected_id]
                   
                    # Calculate additional metrics for research
                    latest_exam = exam_data.sort_values("exam_date").iloc[-1] if not exam_data.empty else None
                    risk_flags = exam_data['flag'].value_counts().to_dict() if not exam_data.empty else {}
                   
                    log_feature_interaction(current_user, "pdf_report_generation", {
                        "student_id": selected_id,
                        "student_name": selected_name,
                        "report_type": "meeting_prep",
                        "num_exams": len(exam_data),
                        "has_epc_data": len(epc_data) > 0,
                        "has_qlf_data": len(qlf_data) > 0,
                        "latest_score": latest_exam['total_score'] if latest_exam is not None else None,
                        "latest_flag": latest_exam['flag'] if latest_exam is not None else None,
                        "step1_pass_prob": latest_exam.get('step1_pass_prob') if latest_exam is not None else None,
                        "risk_flag_distribution": risk_flags,
                        "exam_types_included": exam_data['exam_type'].unique().tolist() if not exam_data.empty else [],
                        "cohort_year": students[students["student_id"] == selected_id].iloc[0]['cohort_year'],
                        "report_generation_context": selected_exam_label,
                        "advisor_preparation_time": datetime.datetime.now().isoformat()
                    })
                   
                    # Offer download
                    st.download_button(
                        label="📥 Download Report",
                        data=pdf_buffer.getvalue(),
                        file_name=f"Student_Report_{selected_name.replace(', ', '_')}_{datetime.datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                   
                    st.success("✅ Report generated successfully! Perfect for advisor meeting preparation.")
                   
                    # Show quick analytics feedback to the user
                    analytics_file = "experiment_analytics.json"
                    if os.path.exists(analytics_file):
                        try:
                            # Count how many reports this user has generated
                            with open(analytics_file, "r") as f:
                                user_pdf_count = 0
                                for line in f:
                                    data = json.loads(line.strip())
                                    if (data.get('user_email') == current_user and
                                        data.get('action') == 'feature_interaction' and
                                        data.get('details', {}).get('feature') == 'pdf_report_generation'):
                                        user_pdf_count += 1
                           
                            if user_pdf_count > 1:
                                st.info(f"📊 **Your Impact**: You've generated {user_pdf_count} meeting prep reports total - great advisor engagement!")
                        except:
                            pass  # Silent fail if analytics can't be read
                   
                except Exception as e:
                    st.error(f"Error generating report: {str(e)}")
                    st.info("💡 **Tip**: Make sure the student has exam data available for report generation.")
   
    with col2:
        if st.button(f"🔍 Access {student_first_name}'s INSIGHTS®", use_container_width=True):
            # Log the insights access attempt for analytics
            log_feature_interaction(current_user, "insights_access_attempt", {
                "student_id": selected_id,
                "student_name": selected_name,
                "student_first_name": student_first_name,
                "access_context": selected_exam_label,
                "cohort_year": students[students["student_id"] == selected_id].iloc[0]['cohort_year'],
                "access_time": datetime.datetime.now().isoformat(),
                "feature_interest": "student_insights_portal"
            })
           
            # Show coming soon message
            st.info("🚧 **Coming Soon!** Student INSIGHTS® portal is in development. This feature will provide personalized study recommendations and performance analytics directly to students.")
            st.success("📊 **Thanks for your interest!** Your feedback helps us prioritize new features.")
   
    st.markdown("---")

    # Show additional metrics when specific exam is selected
    if selected_exam_label != "All" and not student_exams.empty:
        exam_data = student_exams.iloc[0]  # Get the specific exam data
       
        col1, col2, col3 = st.columns(3)
       
        with col1:
            if 'step1_pass_prob' in exam_data.index:
                pass_prob = exam_data['step1_pass_prob']
                st.metric("Step 1 Pass Probability", f"{pass_prob:.1%}")
       
        with col2:
            if 'band' in exam_data.index:
                band = exam_data['band']
                st.metric("Performance Band", band)
       
        with col3:
            total_score = exam_data['total_score']
            flag_color = exam_data['flag']
            readiness_status = get_readiness_status(flag_color)
            readiness_emoji = get_readiness_emoji(flag_color)
           
            st.metric("Total Score", f"{total_score}")
            st.markdown(f"**Step 1 Readiness:** {readiness_emoji} {readiness_status}")
       
        # Additional context box
        if 'step1_pass_prob' in exam_data.index:
            pass_prob = exam_data['step1_pass_prob']
            if pass_prob >= 0.8:
                st.success(f"🎯 **Strong performance**: {pass_prob:.1%} probability of Step 1 success")
            elif pass_prob >= 0.6:
                st.warning(f"⚠️ **Moderate risk**: {pass_prob:.1%} probability of Step 1 success - consider targeted intervention")
            else:
                st.error(f"🚨 **High risk**: {pass_prob:.1%} probability of Step 1 success - immediate intervention recommended")
       
        st.markdown("---")

    # Exam History
    st.subheader("📊 Exam History")
    
    # Check if student has any exam data
    if student_exams.empty:
        st.warning("⚠️ No exam data available for this student.")
        # Track user frustration when no exam data found
        log_user_frustration(current_user, "no_exam_data", {
            "student_id": selected_id,
            "student_name": selected_name,
            "exam_filter": selected_exam_label
        })
    else:
        # Prepare exam data for display
        styled_exams = student_exams.sort_values("exam_date").copy().reset_index(drop=True)

        # Track that user successfully viewed exam data
        log_workflow_stage(current_user, "student_analysis", "data_viewed", {
            "student_id": selected_id,
            "num_exams": len(styled_exams)
        })
   
    # Create display version with readiness terminology
    exam_display = styled_exams.copy()
    exam_display['Readiness Status'] = exam_display['flag'].apply(get_readiness_status)
   
    # Reorder columns to put Readiness Status where flag was, then remove flag
    cols = list(exam_display.columns)
    if 'flag' in cols:
        flag_idx = cols.index('flag')
        cols[flag_idx] = 'Readiness Status'  # Replace flag with Readiness Status
        # Remove the original Readiness Status from the end and keep it in flag position
        if 'Readiness Status' in cols[flag_idx+1:]:
            remaining_cols = [c for c in cols if c != 'Readiness Status']
            remaining_cols.insert(flag_idx, 'Readiness Status')
            cols = remaining_cols
   
    # Remove internal flag column and reorder
    display_cols = [col for col in cols if col != 'flag']
    exam_display = exam_display[display_cols]
   
    # Simple color styling function
    def highlight_readiness_status(val):
        """Style individual readiness status cells"""
        if val == "Step 1 Ready":
            return "background-color: #d4edda; color: #155724; font-weight: bold"
        elif val == "Approaching Readiness":
            return "background-color: #fff3cd; color: #856404; font-weight: bold"
        elif val == "Below Readiness Threshold":
            return "background-color: #f8d7da; color: #721c24; font-weight: bold"
        return ""
   
    # Apply styling only to the Readiness Status column
    if 'Readiness Status' in exam_display.columns:
        styled_exam_display = exam_display.style.map(highlight_readiness_status, subset=['Readiness Status'])
        st.dataframe(styled_exam_display, use_container_width=True)
    else:
        st.dataframe(exam_display, use_container_width=True)

    # Score trend over time
    if selected_exam_label == "All" and not student_exams.empty:
        st.subheader("📈 Score Trend Over Time")
        
        # Check what exam types this student has
        exam_types_available = student_exams['exam_type'].unique()
        
        if len(exam_types_available) > 1:
            # Apply same separation logic as EPC section
            st.info("💡 **Note**: CBSE and CBSSA assess different constructs and scores are not directly comparable")
            
            # Create separate charts for each exam type (matching EPC approach)
            for exam_type in sorted(exam_types_available):
                exam_type_data = student_exams[student_exams['exam_type'] == exam_type].copy()
                
                if not exam_type_data.empty:
                    st.markdown(f"**{exam_type} Score Timeline** (n={len(exam_type_data)})")
                    
                    # Create base chart for this exam type
                    base_chart = alt.Chart(exam_type_data)
                    
                    # Background shaded zones for readiness levels
                    red_zone = alt.Chart(pd.DataFrame({'y': [0], 'y2': [62]})).mark_rect(
                        opacity=0.1, color='red'
                    ).encode(
                        y=alt.Y('y:Q', scale=alt.Scale(domain=[30, 95])),
                        y2='y2:Q'
                    )
                    
                    yellow_zone = alt.Chart(pd.DataFrame({'y': [62], 'y2': [66]})).mark_rect(
                        opacity=0.1, color='orange'
                    ).encode(
                        y='y:Q',
                        y2='y2:Q'
                    )
                    
                    green_zone = alt.Chart(pd.DataFrame({'y': [66], 'y2': [95]})).mark_rect(
                        opacity=0.1, color='green'
                    ).encode(
                        y='y:Q',
                        y2='y2:Q'
                    )
                    
                    # Reference lines
                    line_62 = alt.Chart(pd.DataFrame({'threshold': [62]})).mark_rule(
                        color='orange', strokeDash=[5, 5], size=2
                    ).encode(y='threshold:Q')
                    
                    line_66 = alt.Chart(pd.DataFrame({'threshold': [66]})).mark_rule(
                        color='green', strokeDash=[5, 5], size=2
                    ).encode(y='threshold:Q')
                    
                    # Color coding by exam type (matching EPC approach)
                    chart_color = 'steelblue' if exam_type == 'CBSE' else 'darkgreen'
                    
                    # Main score trend for this exam type only
                    score_trend_chart = base_chart.mark_circle(size=100, color=chart_color).encode(
                        x=alt.X("exam_date:T", title="Exam Date"),
                        y=alt.Y("total_score:Q", title="Score", scale=alt.Scale(domain=[30, 95])),
                        tooltip=["exam_type", "exam_date", "total_score"]
                    )
                    
                    # Add connecting line if multiple exams of same type
                    if len(exam_type_data) > 1:
                        line_chart = base_chart.mark_line(color=chart_color, strokeWidth=2).encode(
                            x=alt.X("exam_date:T"),
                            y=alt.Y("total_score:Q")
                        )
                        score_trend_chart = score_trend_chart + line_chart
                    
                    # Combine all layers
                    combined_chart = (red_zone + yellow_zone + green_zone + line_62 + line_66 + score_trend_chart).resolve_scale(
                        y='shared'
                    ).properties(
                        height=300,
                        title=f"{exam_type} Score Progression with Step 1 Readiness Zones"
                    )
                    
                    st.altair_chart(combined_chart, use_container_width=True)
        else:
            # Single exam type - use original chart
            exam_type = exam_types_available[0]
            st.markdown(f"**{exam_type} Score Timeline** (n={len(student_exams)})")
            
            # Create base chart with reference zones
            base_chart = alt.Chart(student_exams)
            
            # Background shaded zones for readiness levels
            red_zone = alt.Chart(pd.DataFrame({'y': [0], 'y2': [62]})).mark_rect(
                opacity=0.1, color='red'
            ).encode(
                y=alt.Y('y:Q', scale=alt.Scale(domain=[30, 95])),
                y2='y2:Q'
            )
            
            yellow_zone = alt.Chart(pd.DataFrame({'y': [62], 'y2': [66]})).mark_rect(
                opacity=0.1, color='orange'
            ).encode(
                y='y:Q',
                y2='y2:Q'
            )
            
            green_zone = alt.Chart(pd.DataFrame({'y': [66], 'y2': [95]})).mark_rect(
                opacity=0.1, color='green'
            ).encode(
                y='y:Q',
                y2='y2:Q'
            )
            
            # Reference lines
            line_62 = alt.Chart(pd.DataFrame({'threshold': [62]})).mark_rule(
                color='orange', strokeDash=[5, 5], size=2
            ).encode(y='threshold:Q')
            
            line_66 = alt.Chart(pd.DataFrame({'threshold': [66]})).mark_rule(
                color='green', strokeDash=[5, 5], size=2
            ).encode(y='threshold:Q')
            
            # Color by exam type
            chart_color = 'steelblue' if exam_type == 'CBSE' else 'darkgreen'
            
            # Main score trend
            score_trend_chart = base_chart.mark_circle(size=100, color=chart_color).encode(
                x=alt.X("exam_date:T", title="Exam Date"),
                y=alt.Y("total_score:Q", title="Score", scale=alt.Scale(domain=[30, 95])),
                tooltip=["exam_type", "exam_date", "total_score"]
            )
            
            # Add connecting line if multiple exams
            if len(student_exams) > 1:
                line_chart = base_chart.mark_line(color=chart_color, strokeWidth=2).encode(
                    x=alt.X("exam_date:T"),
                    y=alt.Y("total_score:Q")
                )
                score_trend_chart = score_trend_chart + line_chart
            
            # Combine all layers
            combined_chart = (red_zone + yellow_zone + green_zone + line_62 + line_66 + score_trend_chart).resolve_scale(
                y='shared'
            ).properties(
                height=350,
                title=f"{exam_type} Score Progression with Step 1 Readiness Zones"
            )
            
            st.altair_chart(combined_chart, use_container_width=True)
        
        # Add legend explanation
        st.markdown("""
        **📊 Readiness Zones:**
        - 🟢 **Green Zone (66+)**: Step 1 Ready
        - 🟡 **Yellow Zone (62-65)**: Approaching Readiness  
        - 🔴 **Red Zone (<62)**: Below Readiness Threshold
        """)
        
        # Log chart interaction with separation tracking
        log_feature_interaction(current_user, "score_trend_chart", {
            "student_id": selected_id,
            "num_exams": len(student_exams),
            "chart_enhanced": "readiness_zones_added_separated_constructs",
            "exam_types": list(exam_types_available),
            "charts_separated": len(exam_types_available) > 1
        })

    # EPC
    st.subheader("📚 EPC Content Area Scores")

    if not student_epc.empty:
        # Identify EPC content columns more carefully
        id_vars = ["student_id", "exam_type", "exam_date"]
        if 'exam_round' in student_epc.columns:
            id_vars.append('exam_round')
        
        # Get content area columns (exclude metadata columns)
        exclude_cols = set(id_vars + ['total_score', 'flag', 'cohort_year', 'step1_pass_prob', 
                                      'step1_ready', 'in_low_pass_range', 'band', 'exam_order', 
                                      'month', 'year_offset', 'exam_year', 'first_name', 'last_name', 
                                      'full_name', 'exam_label'])
        
        content_cols = [col for col in student_epc.columns if col not in exclude_cols]
        
        if content_cols:
            st.write(f"**Found {len(content_cols)} content areas**")
            
            # Melt the data properly
            epc_long = student_epc.melt(
                id_vars=id_vars,
                value_vars=content_cols,
                var_name="EPC", 
                value_name="Score"
            )
            
            # Convert Score to numeric, handling non-numeric values
            epc_long["Score"] = pd.to_numeric(epc_long["Score"], errors='coerce')
            
            # Remove rows with NaN scores and filter out zero scores that might be missing data
            epc_long = epc_long.dropna(subset=["Score"]).copy()
            epc_long = epc_long[epc_long["Score"] > 0].copy()  # Remove likely missing data zeros
            
            if not epc_long.empty:
                # Show sample size information (addressing psychometric feedback)
                st.info(f"📊 **Sample Information**: Showing {len(epc_long)} content area scores across {len(epc_long['EPC'].unique())} different areas")


                # Additional validation for synthetic data issues
                zero_scores_filtered = len(student_epc.melt(id_vars=id_vars, value_vars=content_cols, var_name="EPC", value_name="Score").query("Score == 0"))
                if zero_scores_filtered > 0:
                    st.warning(f"⚠️ **Data Quality Note**: {zero_scores_filtered} content area scores showing as 0% have been filtered out (likely synthetic data artifacts)")
                    # Track when users see data quality warnings
                    log_feature_interaction(current_user, "data_quality_warning_shown", {
                        "warning_type": "zero_scores_filtered",
                        "count": zero_scores_filtered,
                        "context": "epc_analysis",
                        "student_id": selected_id
                    })
                
                # Check for unrealistic score patterns that might indicate synthetic data issues
                perfect_scores = len(epc_long[epc_long["Score"] == 100])
                if perfect_scores > len(epc_long) * 0.3:  # More than 30% perfect scores
                    st.info("📊 **Data Note**: High number of perfect scores detected - this may reflect synthetic data patterns")
                    # Track when users see synthetic data patterns
                    log_feature_interaction(current_user, "data_quality_warning_shown", {
                        "warning_type": "perfect_scores_detected",
                        "count": perfect_scores,
                        "percentage": (perfect_scores / len(epc_long)) * 100,
                        "context": "epc_analysis",
                        "student_id": selected_id
                    })
                
                # Create separate charts for each exam type (addressing feedback about separating CBSE/CBSSA)
                exam_types = epc_long['exam_type'].unique()
                
                if len(exam_types) > 1:
                    st.markdown("**📊 Content Performance by Exam Type**")
                    st.info("💡 **Note**: CBSE and CBSSA assess different constructs and scores are not directly comparable")
                    
                    for exam_type in sorted(exam_types):
                        exam_epc = epc_long[epc_long['exam_type'] == exam_type].copy()
                        
                        if not exam_epc.empty:
                            st.markdown(f"**{exam_type} Content Areas** (n={len(exam_epc)})")
                            
                            # Create chart
                            chart_color = 'steelblue' if exam_type == 'CBSE' else 'darkgreen'
                            
                            epc_chart = alt.Chart(exam_epc).mark_bar(
                                color=chart_color
                            ).encode(
                                x=alt.X("EPC:N", sort="-y", title="Content Area", axis=alt.Axis(labelAngle=-45)),
                                y=alt.Y("Score:Q", title="Score %"),
                                tooltip=["EPC:N", "Score:Q"]
                            ).properties(
                                width=600,
                                height=300,
                                title=f"{exam_type} Content Area Performance"
                            )
                            
                            st.altair_chart(epc_chart, use_container_width=True)
                            
                            # Enhanced Top areas for improvement with better data validation
                            st.markdown(f"**{exam_type} - Top Areas for Improvement:**")
                            weakest_epcs = exam_epc.sort_values("Score").head(5)
                            
                            if not weakest_epcs.empty and weakest_epcs["Score"].sum() > 0:  # Ensure we have valid scores
                                for _, row in weakest_epcs.iterrows():
                                    score = row['Score']
                                    if score == 0:
                                        st.markdown(f"🔧 **{row['EPC']}**: Data unavailable (synthetic data issue)")
                                    elif score < 70:
                                        st.markdown(f"🔴 **{row['EPC']}**: {score:.1f}% - High Priority")
                                    elif score < 80:
                                        st.markdown(f"🟡 **{row['EPC']}**: {score:.1f}% - Monitor")
                                    else:
                                        st.markdown(f"🟢 **{row['EPC']}**: {score:.1f}% - Acceptable")
                            else:
                                st.warning("⚠️ **Areas for Improvement data unavailable** - this may be due to synthetic data limitations or data processing issues")
                                st.info("💡 **For prototype purposes**: This section will show the lowest-performing content areas when real data is available")
                        else:
                            st.warning(f"No {exam_type} data to display")
                else:
                    # Single exam type
                    exam_type = exam_types[0]
                    st.markdown(f"**{exam_type} Content Areas** (n={len(epc_long)})")
                    
                    chart_color = 'steelblue' if exam_type == 'CBSE' else 'darkgreen'
                    
                    epc_chart = alt.Chart(epc_long).mark_bar(
                        color=chart_color
                    ).encode(
                        x=alt.X("EPC:N", sort="-y", title="Content Area", axis=alt.Axis(labelAngle=-45)),
                        y=alt.Y("Score:Q", title="Score %"),
                        tooltip=["EPC:N", "Score:Q"]
                    ).properties(
                        width=600,
                        height=300,
                        title="Content Area Performance"
                    )
                    
                    st.altair_chart(epc_chart, use_container_width=True)
                    
                    # Top areas for improvement
                    st.markdown("**Top Areas for Improvement:**")
                    weakest_epcs = epc_long.sort_values("Score").head(5)
                    for _, row in weakest_epcs.iterrows():
                        if row['Score'] < 70:
                            st.markdown(f"🔴 **{row['EPC']}**: {row['Score']:.1f}% - High Priority")
                        elif row['Score'] < 80:
                            st.markdown(f"🟡 **{row['EPC']}**: {row['Score']:.1f}% - Monitor")
                        else:
                            st.markdown(f"🟢 **{row['EPC']}**: {row['Score']:.1f}% - Acceptable")
                
                # Log EPC interaction
                log_feature_interaction(current_user, "epc_analysis", {
                    "student_id": selected_id,
                    "num_content_areas": len(epc_long["EPC"].unique()),
                    "weakest_area": epc_long.sort_values("Score").iloc[0]["EPC"] if not epc_long.empty else None,
                    "exam_types": list(exam_types),
                    "separated_by_exam_type": len(exam_types) > 1
                })
            else:
                st.warning("⚠️ **No valid EPC scores found**. This could mean:")
                st.markdown("- All scores are 0 (indicating missing data)")
                st.markdown("- Data format issues")
                st.markdown("- No content area data for this student/exam combination")
        else:
            st.warning("⚠️ **No content area columns identified** in the EPC data")
            st.markdown("This might be a data structure issue that needs investigation.")
    else:
        st.write("No EPC data available for this student.")

    # Enhanced QLF - Question-Level Feedback
    st.subheader("🔍 Question-Level Performance Analysis")
    if not student_qlf.empty:
        # Ensure 'correct' column is numeric and clean data
        student_qlf["correct"] = pd.to_numeric(student_qlf["correct"], errors='coerce')
        student_qlf["national_pct_correct"] = pd.to_numeric(student_qlf["national_pct_correct"], errors='coerce')
       
        # Remove rows with invalid data
        student_qlf_clean = student_qlf.dropna(subset=["correct", "physician_competency", "content_topic", "content_description"]).copy()
       
        if not student_qlf_clean.empty:
            # Quick summary metrics
            col1, col2, col3, col4 = st.columns(4)
           
            total_questions = len(student_qlf_clean)
            correct_answers = student_qlf_clean["correct"].sum()
            overall_pct = (correct_answers / total_questions) * 100
            below_national = len(student_qlf_clean[(student_qlf_clean["correct"] == 0) &
                                                   (student_qlf_clean["national_pct_correct"] >= 70)])
           
            with col1:
                st.metric("Total Questions", total_questions)
            with col2:
                st.metric("Overall Correct", f"{correct_answers}/{total_questions}")
            with col3:
                st.metric("Overall %", f"{overall_pct:.1f}%")
            with col4:
                st.metric("Missed High-Yield", below_national, help="Questions missed with >70% national average")
           
            # Filtering options
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
           
            with col1:
                show_filter = st.selectbox(
                    "Show Questions",
                    ["All Questions", "Incorrect Only", "Below National Average"],
                    help="Filter questions by performance"
                )
           
            with col2:
                competency_filter = st.selectbox(
                    "Physician Competency",
                    ["All"] + sorted(student_qlf_clean["physician_competency"].unique()),
                    help="Filter by competency area"
                )
           
            with col3:
                topic_filter = st.selectbox(
                    "Content Topic",
                    ["All"] + sorted(student_qlf_clean["content_topic"].unique()),
                    help="Filter by content topic"
                )
           
            # Apply filters
            filtered_qlf = student_qlf_clean.copy()
           
            if show_filter == "Incorrect Only":
                filtered_qlf = filtered_qlf[filtered_qlf["correct"] == 0]
            elif show_filter == "Below National Average":
                filtered_qlf = filtered_qlf[
                    (filtered_qlf["correct"] == 0) &
                    (filtered_qlf["national_pct_correct"] >= 70)
                ]
           
            if competency_filter != "All":
                filtered_qlf = filtered_qlf[filtered_qlf["physician_competency"] == competency_filter]
           
            if topic_filter != "All":
                filtered_qlf = filtered_qlf[filtered_qlf["content_topic"] == topic_filter]
           
            # Create display dataframe
            if not filtered_qlf.empty:
                display_qlf = filtered_qlf.copy()
               
                # Create the status column with visual indicators
                display_qlf["Status"] = display_qlf["correct"].apply(lambda x: "✅ Correct" if x == 1 else "❌ Incorrect")
               
                # Create exam take column
                display_qlf["Exam Take"] = display_qlf["exam_round"].astype(str) + " | " + display_qlf["exam_date"]
               
                # Performance vs national
                display_qlf["Vs National"] = display_qlf.apply(
                    lambda row: "Above Avg" if row["correct"] == 1 and row["national_pct_correct"] < 80
                    else "Expected" if row["correct"] == 1
                    else "Below Avg" if row["correct"] == 0 and row["national_pct_correct"] >= 70
                    else "Acceptable Miss" if row["correct"] == 0 and row["national_pct_correct"] < 70
                    else "Miss",
                    axis=1
                )
               
                # Format national percentage
                display_qlf["National %"] = display_qlf["national_pct_correct"].apply(lambda x: f"{x:.0f}%")
               
                # Select and rename columns for display
                final_display = display_qlf[[
                    "Status", "physician_competency", "content_topic", "content_description",
                    "National %", "Vs National", "Exam Take"
                ]].copy()
               
                final_display = final_display.rename(columns={
                    "physician_competency": "Physician Competency",
                    "content_topic": "Content Topic",
                    "content_description": "Content Description"
                })
               
                # Sort by incorrect first, then by national percentage (high to low)
                sort_order = display_qlf["correct"].astype(str) + display_qlf["national_pct_correct"].apply(lambda x: f"{100-x:03.0f}")
                final_display = final_display.iloc[sort_order.argsort()]
               
                # Style the dataframe
                def highlight_status(row):
                    colors = []
                    for col in row.index:
                        if col == 'Status':
                            if '❌' in str(row[col]):
                                colors.append('background-color: #f8d7da; color: #721c24; font-weight: bold')
                            elif '✅' in str(row[col]):
                                colors.append('background-color: #d4edda; color: #155724; font-weight: bold')
                            else:
                                colors.append('')
                        elif col == 'Vs National':
                            if 'Below Avg' in str(row[col]):
                                colors.append('background-color: #fff3cd; color: #856404; font-weight: bold')
                            elif 'Above Avg' in str(row[col]):
                                colors.append('background-color: #d1ecf1; color: #0c5460; font-weight: bold')
                            else:
                                colors.append('')
                        else:
                            colors.append('')
                    return colors
               
                # Display the table
                st.markdown(f"**Showing {len(final_display)} questions** (filtered from {total_questions} total)")
               
                styled_qlf = final_display.style.apply(highlight_status, axis=1)
                st.dataframe(styled_qlf, use_container_width=True, height=400)
               
                # Key insights summary
                st.markdown("---")
                st.markdown("### 🎯 Key Insights")
               
                col1, col2 = st.columns(2)
               
                with col1:
                    # Competency performance
                    comp_summary = student_qlf_clean.groupby("physician_competency").agg({
                        "correct": ["count", "sum"]
                    })
                    comp_summary.columns = ["Total", "Correct"]
                    comp_summary["% Correct"] = (comp_summary["Correct"] / comp_summary["Total"]) * 100
                    comp_summary = comp_summary.sort_values("% Correct")
                   
                    st.markdown("**Performance by Competency:**")
                    for comp, row in comp_summary.iterrows():
                        pct = row["% Correct"]
                        if pct < 60:
                            emoji = "🚨"
                        elif pct < 75:
                            emoji = "⚠️"
                        else:
                            emoji = "✅"
                        st.markdown(f"{emoji} **{comp}**: {pct:.1f}% ({row['Correct']}/{row['Total']})")
               
                with col2:
                    # High-yield misses (questions >75% national average that were missed)
                    high_yield_missed = student_qlf_clean[
                        (student_qlf_clean["correct"] == 0) &
                        (student_qlf_clean["national_pct_correct"] >= 75)
                    ].sort_values("national_pct_correct", ascending=False)
                   
                    st.markdown("**High-Yield Topics Missed:**")
                    if not high_yield_missed.empty:
                        for _, row in high_yield_missed.head(5).iterrows():
                            st.markdown(f"🎯 **{row['content_topic']}**: {row['content_description'][:50]}... ({row['national_pct_correct']:.0f}% national)")
                    else:
                        st.success("🎉 No high-yield topics missed!")
               
                # Log enhanced QLF interaction
                log_feature_interaction(current_user, "enhanced_qlf_analysis", {
                    "student_id": selected_id,
                    "total_questions": total_questions,
                    "questions_displayed": len(final_display),
                    "filter_applied": show_filter,
                    "competency_filter": competency_filter,
                    "topic_filter": topic_filter,
                    "overall_performance": overall_pct,
                    "high_yield_missed": len(high_yield_missed)
                })
               
            else:
                st.info("No questions match the selected filters. Try adjusting your filter criteria.")
               
        else:
            st.write("No valid QLF data found after data cleaning.")
    else:
        st.write("No QLF data available.")

# --- AT-RISK STUDENT TRIAGE ---
elif page == "At-Risk Student Triage":
    st.markdown("# 🚨 At-Risk Student Triage")
    st.markdown("*Identify and prioritize students needing immediate academic intervention*")
   
    try:
        # Triage Filters
        st.sidebar.header("Triage Filters")
       
        # Basic data merge
        triage_base_data = exam_records.merge(students[['student_id', 'cohort_year']], on='student_id')
       
        # Cohort filter
        available_cohorts = sorted(triage_base_data['cohort_year'].unique(), reverse=True)
        selected_cohort = st.sidebar.selectbox("Select Cohort", ["All Cohorts"] + [str(c) for c in available_cohorts])
       
        # Risk level filter
        risk_levels = st.sidebar.multiselect(
            "Step 1 Readiness Levels",
            ["Red", "Yellow", "Green"],
            default=[],  # No default selection
            format_func=get_readiness_status  # Show professional terminology in dropdown
        )
       
        # Exam recency filter
        exam_filter = st.sidebar.selectbox("Based on Exam", ["Most Recent", "All Exams"])
       
        if risk_levels:
            # Apply filtering
            triage_data = triage_base_data.copy()
           
            # Apply cohort filter
            if selected_cohort != "All Cohorts":
                triage_data = triage_data[triage_data['cohort_year'] == int(selected_cohort)]
           
            # Apply risk level filter  
            triage_data = triage_data[triage_data['flag'].isin(risk_levels)]
           
            # Apply exam recency filter
            if exam_filter == "Most Recent":
                # Get most recent exam for each student
                triage_data['exam_date'] = pd.to_datetime(triage_data['exam_date'])
                triage_data = triage_data.loc[triage_data.groupby('student_id')['exam_date'].idxmax()]
           
            # Log triage usage
            log_triage_usage(current_user, selected_cohort, risk_levels, exam_filter, len(triage_data))
           
            if not triage_data.empty:
                # Summary metrics
                st.subheader("🎯 Triage Summary")
                col1, col2, col3, col4 = st.columns(4)
               
                with col1:
                    total_at_risk = len(triage_data)
                    st.metric("Students Requiring Attention", total_at_risk)
               
                with col2:
                    high_risk_count = len(triage_data[triage_data['flag'] == 'Red'])
                    st.metric("Below Readiness Threshold", high_risk_count)
               
                with col3:
                    moderate_risk_count = len(triage_data[triage_data['flag'] == 'Yellow'])
                    st.metric("Approaching Readiness", moderate_risk_count)
               
                with col4:
                    if 'step1_pass_prob' in triage_data.columns:
                        avg_pass_prob = triage_data['step1_pass_prob'].mean()
                        st.metric("Avg Step 1 Pass Probability", f"{avg_pass_prob:.1%}")
                    else:
                        low_pass_count = len(triage_data[triage_data['total_score'] < 66])
                        st.metric("Below Pass Threshold", low_pass_count)
               
                # Student list
                st.subheader("📋 Priority Student List")
               
                # Add student names
                triage_data = triage_data.merge(students[['student_id', 'first_name', 'last_name']], on='student_id', how='left')
                triage_data['full_name'] = triage_data['last_name'] + ", " + triage_data['first_name']
               
                # Sort by risk level and score
                risk_order = {'Red': 1, 'Yellow': 2, 'Green': 3}
                triage_data['risk_order'] = triage_data['flag'].map(risk_order)
                triage_data = triage_data.sort_values(['risk_order', 'total_score'])
               
                # Prepare display columns
                display_cols = ['full_name', 'cohort_year', 'exam_type', 'exam_date', 'total_score', 'flag']
                if 'step1_pass_prob' in triage_data.columns:
                    display_cols.append('step1_pass_prob')
                if 'band' in triage_data.columns:
                    display_cols.append('band')
               
                display_data = triage_data[display_cols].copy()
               
                # Convert flag to readiness terminology for display
                display_data['Step 1 Readiness'] = display_data['flag'].apply(get_readiness_status)
                
                # Keep original flag for styling by adding it as a hidden helper column
                display_data['_original_flag'] = display_data['flag']
               
                # Rename columns for display
                column_renames = {
                    'full_name': 'Student Name',
                    'cohort_year': 'Cohort',
                    'exam_type': 'Exam Type',
                    'exam_date': 'Date',
                    'total_score': 'Score',
                    'step1_pass_prob': 'Step 1 Pass Prob',
                    'band': 'Performance Band'
                }
               
                # Only rename columns that exist
                display_data = display_data.rename(columns={k: v for k, v in column_renames.items() if k in display_data.columns})
               
                # Remove internal flag column but keep the hidden helper
                if 'flag' in display_data.columns:
                    display_data = display_data.drop(['flag'], axis=1)
               
                # Format Step 1 probability
                if 'Step 1 Pass Prob' in display_data.columns:
                    display_data['Step 1 Pass Prob'] = display_data['Step 1 Pass Prob'].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "N/A")
               
                # Style the dataframe with color coding
                def highlight_readiness(row):
                    colors = []
                    flag_val = row['_original_flag']  # Get flag directly from the row
                    for col in row.index:
                        if col == 'Step 1 Readiness':
                            colors.append(get_readiness_color_style(flag_val) + " font-weight: bold")
                        else:
                            colors.append("")
                    return colors
               
                # Style the dataframe with color coding using a simpler approach
                def highlight_readiness_simple(val):
                    """Color code the readiness status based on the text value"""
                    if val == "Below Readiness Threshold":
                        return "background-color: #f8d7da; color: #721c24; font-weight: bold"
                    elif val == "Approaching Readiness":
                        return "background-color: #fff3cd; color: #856404; font-weight: bold"
                    elif val == "Step 1 Ready":
                        return "background-color: #d4edda; color: #155724; font-weight: bold"
                    return ""
               
                # Remove the helper column for final display
                final_display = display_data.drop('_original_flag', axis=1)
                
                # Apply styling to the Step 1 Readiness column only
                styled_df_final = final_display.style.map(
                    highlight_readiness_simple, 
                    subset=['Step 1 Readiness']
                )
                
                st.dataframe(styled_df_final, use_container_width=True)
                
                # Debug option to check data consistency
                if st.checkbox("🔍 Debug: Check data consistency", key="triage_debug"):
                    st.markdown("**Data Consistency Check:**")
                    debug_data = triage_data[['full_name', 'total_score', 'flag', 'band']].head(10)
                    
                    # Add expected values
                    debug_data['Expected Flag'] = debug_data['total_score'].apply(
                        lambda x: "Green" if x >= 66 else "Yellow" if x >= 62 else "Red"
                    )
                    debug_data['Expected Band'] = debug_data['total_score'].apply(
                        lambda x: "Above Low Pass Range" if x >= 66 else "In Low Pass Range" if x >= 62 else "Below Low Pass Range"
                    )
                    
                    # Check for mismatches
                    debug_data['Flag Match'] = debug_data['flag'] == debug_data['Expected Flag']
                    debug_data['Band Match'] = debug_data['band'] == debug_data['Expected Band']
                    
                    st.dataframe(debug_data, use_container_width=True)
               
                # Action buttons
                st.subheader("📤 Actions")
                col1, col2 = st.columns(2)
               
                with col1:
                    if st.button("📋 Export Student List to CSV"):
                        csv = display_data.to_csv(index=False)
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"at_risk_students_{selected_cohort}_{exam_filter.replace(' ', '_')}.csv",
                            mime="text/csv"
                        )
                        # Log export action
                        log_feature_interaction(current_user, "export_triage_list", {
                            "cohort": selected_cohort,
                            "risk_levels": risk_levels,
                            "student_count": len(display_data)
                        })
               
                with col2:
                    st.markdown("**Quick Actions:**")
                    st.markdown("• Schedule advisor meetings")
                    st.markdown("• Assign learning specialists")
                    st.markdown("• Create intervention plans")
               
                # Risk insights
                if high_risk_count > 0:
                    st.warning(f"⚠️ **{high_risk_count} students below readiness threshold** - immediate intervention recommended")
                if moderate_risk_count > 0:
                    st.info(f"ℹ️ **{moderate_risk_count} students approaching readiness** - monitor closely and consider targeted support")
                   
            else:
                st.info(f"✅ **No students found** matching the selected criteria.")
                st.markdown("**Try adjusting filters:**")
                st.markdown("- Select different risk levels")
                st.markdown("- Change cohort selection")
                st.markdown("- Try 'All Exams' instead of 'Most Recent'")
       
        else:
            st.warning("⚠️ Please select at least one readiness level to begin triage.")
            st.markdown("### 🚨 **Step 1 Readiness Guide:**")
            st.markdown("- **🚨 Below Readiness Threshold**: Score <62 - **Immediate intervention required**")
            st.markdown("- **⚠️ Approaching Readiness**: Score 62-65 - **Monitor closely, consider targeted support**")
            st.markdown("- **✅ Step 1 Ready**: Score ≥66 - **On track for Step 1 success**")
           
    except Exception as e:
        st.error(f"Error in triage page: {str(e)}")
        import traceback
        st.text(traceback.format_exc())

# --- COHORT ANALYTICS ---
elif page == "Cohort Analytics":
    st.markdown("# 📊 Cohort Performance Analytics")
    st.markdown("*Compare cohort performance to previous years and analyze trends*")
   
    # Cohort Selection
    st.sidebar.header("Cohort Filters")
    available_cohorts = sorted(exam_records.merge(students[['student_id', 'cohort_year']], on='student_id')['cohort_year'].unique(), reverse=True)
    selected_cohorts = st.sidebar.multiselect("Select Cohorts to Compare", available_cohorts, default=[])
   
    # Individual Exam Selection
    st.sidebar.header("Exam Filters")
   
    # Get all available exam combinations using exam_round (not individual dates)
    exam_data_for_filter = exam_records.merge(students[['student_id', 'cohort_year']], on='student_id')
   
    # Check if exam_round exists in the data
    if 'exam_round' in exam_data_for_filter.columns:
        # Create exam labels using exam_type + exam_round, replacing MS with ME
        exam_data_for_filter['exam_label'] = exam_data_for_filter['exam_type'] + " - " + exam_data_for_filter['exam_round'].astype(str).str.replace('MS', 'ME')
        # Get unique exam labels (should be exactly 6)
        available_exams = sorted(exam_data_for_filter['exam_label'].unique())
    else:
        # Fallback: use exam_type only if exam_round is missing
        available_exams = sorted(exam_data_for_filter['exam_type'].unique())
        st.warning("⚠️ Exam round data not found. Showing exam types only.")
   
    selected_exams = st.sidebar.multiselect(
        "Select Specific Exams",
        available_exams,
        default=[],  # Default to no exams selected
        help="Select one or more exam types to analyze. Data will be aggregated across selected exams."
    )
   
    # Log cohort analysis usage
    if selected_cohorts and selected_exams:
        log_cohort_analysis(current_user, selected_cohorts, selected_exams)
   
    if selected_cohorts and selected_exams:
        # Merge cohort data
        cohort_data = exam_records.merge(students[['student_id', 'cohort_year']], on='student_id')
        cohort_data = cohort_data[cohort_data['cohort_year'].isin(selected_cohorts)].copy()
       
        # Add exam labels to cohort_data using the same logic
        if 'exam_round' in cohort_data.columns:
            cohort_data['exam_label'] = cohort_data['exam_type'] + " - " + cohort_data['exam_round'].astype(str).str.replace('MS', 'ME')
        else:
            # Fallback: use exam_type only
            cohort_data['exam_label'] = cohort_data['exam_type']
       
        # Filter by selected exams
        cohort_data = cohort_data[cohort_data['exam_label'].isin(selected_exams)].copy()
       
        if cohort_data.empty:
            st.warning("No data available for the selected cohorts and exams.")
        else:
            # Show selected filters
            st.markdown(f"**Analyzing:** {len(selected_cohorts)} cohort(s) across {len(selected_exams)} exam(s)")

            # 🎯 NEW PSYCHOMETRIC TOGGLE FEATURE
            st.subheader("📊 Analysis View Selection")
            st.info("💡 **Psychometric Insight**: Different summary statistics serve different educational purposes. Choose the view that matches your decision-making needs.")
            
            # Toggle for different statistical views
            col1, col2 = st.columns([2, 1])
            
            with col1:
                view_mode = st.selectbox(
                    "📈 Statistical View",
                    ["Mean Scores", "Median Scores", "% Above Threshold (≥66)"],
                    help="Choose the statistical measure that best serves your educational decision-making needs"
                )
            
            with col2:
                st.markdown("**📚 When to Use:**")
                if view_mode == "Mean Scores":
                    st.markdown("• Program comparison")
                    st.markdown("• Research & reporting")
                    st.markdown("• Overall trends")
                elif view_mode == "Median Scores": 
                    st.markdown("• Typical student performance")
                    st.markdown("• Outlier-resistant analysis")
                    st.markdown("• Curriculum evaluation")
                else:  # % Above Threshold
                    st.markdown("• **Intervention planning**")
                    st.markdown("• **Resource allocation**")
                    st.markdown("• **Step 1 readiness counts**")
            
            # Log the toggle usage
            log_feature_interaction(current_user, "psychometric_toggle_usage", {
                "view_mode": view_mode,
                "cohorts_analyzed": selected_cohorts,
                "exams_analyzed": selected_exams,
                "psychometric_feature": "statistical_view_toggle"
            })


            # Overview Statistics (Dynamic based on toggle)
            st.subheader("📈 Cohort Overview")
            col1, col2, col3, col4 = st.columns(4)
           
            with col1:
                total_students = cohort_data['student_id'].nunique()
                st.metric("Total Students", total_students)
           
            with col2:
                # Dynamic calculation based on selected view
                if view_mode == "Mean Scores":
                    summary_score = cohort_data['total_score'].mean()
                    st.metric("Average Score", f"{summary_score:.1f}")
                elif view_mode == "Median Scores":
                    summary_score = cohort_data['total_score'].median() 
                    st.metric("Median Score", f"{summary_score:.1f}")
                else:  # % Above Threshold
                    summary_score = (cohort_data['total_score'] >= 66).mean() * 100
                    st.metric("% Above Threshold (≥66)", f"{summary_score:.1f}%")
           
            with col3:
                pass_rate = (cohort_data['flag'] == 'Green').mean() * 100
                st.metric("Step 1 Ready Rate", f"{pass_rate:.1f}%")
           
            with col4:
                at_risk_rate = (cohort_data['flag'] == 'Red').mean() * 100
                st.metric("Below Readiness Rate", f"{at_risk_rate:.1f}%")
            
            # Psychometric interpretation based on selected view
            if view_mode == "Median Scores":
                median_val = cohort_data['total_score'].median()
                mean_val = cohort_data['total_score'].mean()
                difference = abs(median_val - mean_val)
                
                if difference > 3:
                    st.info(f"📊 **Distribution Insight**: Median ({median_val:.1f}) differs from mean ({mean_val:.1f}) by {difference:.1f} points, suggesting outliers in the data.")
                else:
                    st.success(f"📊 **Distribution Insight**: Median ({median_val:.1f}) and mean ({mean_val:.1f}) are similar, indicating a well-balanced distribution.")
            
            elif view_mode == "% Above Threshold (≥66)":
                threshold_pct = (cohort_data['total_score'] >= 66).mean() * 100
                intervention_needed = len(cohort_data[cohort_data['total_score'] < 66])
                red_flags = (cohort_data['flag'] == 'Red').mean() * 100
                yellow_flags = (cohort_data['flag'] == 'Yellow').mean() * 100
                
                st.info(f"🎯 **Intervention Planning**: {intervention_needed} students ({100-threshold_pct:.1f}%) score below 66 and may benefit from support. This includes {red_flags:.1f}% (Red flags) requiring immediate intervention and {yellow_flags:.1f}% (Yellow flags) approaching readiness.")
                
                # Actionable guidance for finding these students
                st.markdown(f"### 🔍 **How to Find These {intervention_needed} Students:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🚨 For Immediate Intervention (Red flags):**")
                    if len(selected_cohorts) == 1:
                        cohort_text = f"'{selected_cohorts[0]}' cohort"
                    else:
                        cohort_text = "selected cohorts"
                        
                    st.markdown(f"1. Go to **At-Risk Student Triage** (sidebar)")
                    st.markdown(f"2. Select {cohort_text}")
                    st.markdown(f"3. Check **'Red'** readiness level only")
                    st.markdown(f"4. Choose **'Most Recent'** exams")
                    st.markdown(f"5. Export the list for immediate outreach")
                    
                with col2:
                    st.markdown("**⚠️ For Targeted Support (Yellow flags):**")
                    st.markdown(f"1. Go to **At-Risk Student Triage** (sidebar)")
                    st.markdown(f"2. Select {cohort_text}")
                    st.markdown(f"3. Check **'Yellow'** readiness level only")
                    st.markdown(f"4. Choose **'Most Recent'** exams")
                    st.markdown(f"5. Export for follow-up planning")
                
                # Quick action guidance
                st.markdown("---")
                st.success("💡 **Next Steps**: Use the sidebar to navigate to **'At-Risk Student Triage'**, then apply the filters above to find your specific students and export the lists for action.")
                
                # Log the workflow guidance usage (always log when they see this)
                log_feature_interaction(current_user, "intervention_workflow_guidance", {
                    "from_cohort_analysis": True,
                    "students_needing_intervention": intervention_needed,
                    "red_flag_percentage": red_flags,
                    "yellow_flag_percentage": yellow_flags,
                    "cohorts_analyzed": selected_cohorts,
                    "workflow_type": "threshold_based_intervention"
                })
           
            # 🎯 ENHANCED PSYCHOMETRIC SECTION: Score Distribution Analysis
            st.subheader("📊 Score Distribution & Variability Analysis")
            st.info("💡 **Psychometric Insight**: Box plots reveal score distribution patterns that averages alone cannot show. Two cohorts with the same mean (e.g., 70) may have very different variability - one tightly clustered vs. one spread from 50s to 90s.")
           
            # Different views based on cohort and exam selection
            if len(selected_cohorts) == 1 and len(selected_exams) > 1:
                # Single cohort, multiple exams = COMPARISON MODE
                st.markdown("### 🔍 **Exam Comparison Analysis**")
                st.markdown(f"**{selected_cohorts[0]} Cohort** across {len(selected_exams)} exams")
               
                # Enhanced summary with variability focus
                exam_summary = cohort_data.groupby('exam_label').agg({
                    'total_score': ['count', 'mean', 'median', 'std', 'min', 'max', lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
                }).round(1)
               
                exam_summary.columns = ['Sample Size (n)', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Q1 (25%)', 'Q3 (75%)']
                exam_summary['IQR'] = exam_summary['Q3 (75%)'] - exam_summary['Q1 (25%)']
                exam_summary['Range'] = exam_summary['Max'] - exam_summary['Min']
                
                # Add variability interpretation
                exam_summary['Variability'] = exam_summary['Std Dev'].apply(
                    lambda x: "Low (σ<5)" if x < 5 else "Moderate (5≤σ<10)" if x < 10 else "High (σ≥10)"
                )
                
                st.markdown("**📊 Detailed Score Statistics by Exam**")
                st.dataframe(exam_summary, use_container_width=True)
                
                # Highlight variability insights
                st.markdown("**🔍 Variability Insights:**")
                high_var_exams = exam_summary[exam_summary['Std Dev'] >= 10].index.tolist()
                low_var_exams = exam_summary[exam_summary['Std Dev'] < 5].index.tolist()
                
                if high_var_exams:
                    st.warning(f"📈 **High Variability**: {', '.join(high_var_exams)} show wide score distributions (σ≥10) - indicates diverse student performance levels")
                if low_var_exams:
                    st.success(f"📉 **Low Variability**: {', '.join(low_var_exams)} show consistent performance (σ<5) - indicates uniform mastery level")
               
                # Enhanced box plot with more detailed annotations
                base_chart = alt.Chart(cohort_data)
               
                # Background shaded zones for readiness levels  
                red_zone = alt.Chart(pd.DataFrame({'y': [0], 'y2': [62]})).mark_rect(
                    opacity=0.1, color='red'
                ).encode(
                    y=alt.Y('y:Q', scale=alt.Scale(domain=[30, 95])),
                    y2='y2:Q'
                )
               
                yellow_zone = alt.Chart(pd.DataFrame({'y': [62], 'y2': [66]})).mark_rect(
                    opacity=0.1, color='orange'
                ).encode(
                    y='y:Q',
                    y2='y2:Q'
                )
               
                green_zone = alt.Chart(pd.DataFrame({'y': [66], 'y2': [95]})).mark_rect(
                    opacity=0.1, color='green'
                ).encode(
                    y='y:Q',
                    y2='y2:Q'
                )
               
                # Reference lines with labels
                line_62 = alt.Chart(pd.DataFrame({'threshold': [62]})).mark_rule(
                    color='orange', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                line_66 = alt.Chart(pd.DataFrame({'threshold': [66]})).mark_rule(
                    color='green', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                # Enhanced box plot with sample size annotations
                box_chart = base_chart.mark_boxplot(
                    size=40,
                    outliers={'color': 'red', 'size': 30}
                ).encode(
                    x=alt.X('exam_label:N', title='Exam', axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y('total_score:Q', title='Total Score', scale=alt.Scale(domain=[30, 95])),
                    color=alt.Color('exam_label:N', title='Exam')
                )
                
                # Add sample size text annotations
                sample_sizes = cohort_data.groupby('exam_label')['total_score'].count().reset_index()
                sample_sizes.columns = ['exam_label', 'count']
                sample_sizes['y_pos'] = 92  # Position near top
                sample_sizes['label'] = 'n=' + sample_sizes['count'].astype(str)
                
                text_chart = alt.Chart(sample_sizes).mark_text(
                    align='center',
                    baseline='middle',
                    fontSize=10,
                    fontWeight='bold'
                ).encode(
                    x='exam_label:N',
                    y='y_pos:Q',
                    text='label:N'
                )
               
                # Combine all layers
                combined_box_chart = (red_zone + yellow_zone + green_zone + line_62 + line_66 + box_chart + text_chart).resolve_scale(
                    y='shared'
                ).properties(
                    width=600,
                    height=400,
                    title=f"Score Distribution by Exam - {selected_cohorts[0]} Cohort"
                )
               
                st.altair_chart(combined_box_chart, use_container_width=True)
               
                # Enhanced box plot explanation
                st.markdown("""
                **📊 How to Read the Box Plots:**
                - **Box**: Middle 50% of scores (IQR from Q1 to Q3)
                - **Line in Box**: Median score (not affected by outliers)
                - **Whiskers**: Extend to min/max within 1.5×IQR
                - **Red Dots**: Outliers beyond normal range
                - **Sample Size (n)**: Number of students per exam
                - **Wide boxes**: High variability in performance
                - **Narrow boxes**: Consistent performance across students
                """)
               
                # Flag distribution by exam
                flag_data = cohort_data.groupby(['exam_label', 'flag']).size().reset_index(name='count')
               
            elif len(selected_cohorts) > 1 and len(selected_exams) > 1:
                # Multiple cohorts, multiple exams = AGGREGATED MODE
                st.markdown("### 🔍 **Multi-Cohort Aggregated Analysis**")
                st.markdown(f"Aggregated view across {len(selected_exams)} exams and {len(selected_cohorts)} cohorts")
               
                # Aggregate scores by student first, then by cohort
                student_aggregated = cohort_data.groupby(['student_id', 'cohort_year']).agg({
                    'total_score': 'mean',  # Average score across exams for each student
                    'flag': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[0]  # Most common flag
                }).reset_index()
               
                # Enhanced cohort summary with variability focus
                cohort_summary = student_aggregated.groupby('cohort_year').agg({
                    'total_score': ['count', 'mean', 'median', 'std', 'min', 'max', lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
                }).round(1)
               
                cohort_summary.columns = ['Sample Size (n)', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Q1 (25%)', 'Q3 (75%)']
                cohort_summary['IQR'] = cohort_summary['Q3 (75%)'] - cohort_summary['Q1 (25%)']
                cohort_summary['Range'] = cohort_summary['Max'] - cohort_summary['Min']
                
                # Add variability interpretation
                cohort_summary['Variability'] = cohort_summary['Std Dev'].apply(
                    lambda x: "Low (σ<5)" if x < 5 else "Moderate (5≤σ<10)" if x < 10 else "High (σ≥10)"
                )
                
                st.markdown("**📊 Detailed Score Statistics by Cohort**")
                st.dataframe(cohort_summary, use_container_width=True)
                
                # Cohort variability comparison
                st.markdown("**🔍 Cohort Variability Comparison:**")
                most_variable = cohort_summary['Std Dev'].idxmax()
                least_variable = cohort_summary['Std Dev'].idxmin()
                
                st.info(f"📈 **Most Variable**: {most_variable} cohort (σ={cohort_summary.loc[most_variable, 'Std Dev']:.1f}) - wider range of student performance")
                st.info(f"📉 **Most Consistent**: {least_variable} cohort (σ={cohort_summary.loc[least_variable, 'Std Dev']:.1f}) - more uniform student performance")
               
                # Enhanced box plot of aggregated student scores
                base_chart = alt.Chart(student_aggregated)
               
                # Background shaded zones
                red_zone = alt.Chart(pd.DataFrame({'y': [0], 'y2': [62]})).mark_rect(
                    opacity=0.1, color='red'
                ).encode(
                    y=alt.Y('y:Q', scale=alt.Scale(domain=[30, 95])),
                    y2='y2:Q'
                )
               
                yellow_zone = alt.Chart(pd.DataFrame({'y': [62], 'y2': [66]})).mark_rect(
                    opacity=0.1, color='orange'
                ).encode(y='y:Q', y2='y2:Q')
               
                green_zone = alt.Chart(pd.DataFrame({'y': [66], 'y2': [95]})).mark_rect(
                    opacity=0.1, color='green'
                ).encode(y='y:Q', y2='y2:Q')
               
                # Reference lines
                line_62 = alt.Chart(pd.DataFrame({'threshold': [62]})).mark_rule(
                    color='orange', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                line_66 = alt.Chart(pd.DataFrame({'threshold': [66]})).mark_rule(
                    color='green', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                # Enhanced box plot
                box_chart = base_chart.mark_boxplot(
                    size=50,
                    outliers={'color': 'red', 'size': 30}
                ).encode(
                    x=alt.X('cohort_year:N', title='Cohort Year'),
                    y=alt.Y('total_score:Q', title='Average Score (Across Selected Exams)', scale=alt.Scale(domain=[30, 95])),
                    color=alt.Color('cohort_year:N', title='Cohort Year')
                )
                
                # Add sample size annotations
                cohort_sizes = student_aggregated.groupby('cohort_year')['total_score'].count().reset_index()
                cohort_sizes.columns = ['cohort_year', 'count']
                cohort_sizes['y_pos'] = 92
                cohort_sizes['label'] = 'n=' + cohort_sizes['count'].astype(str)
                
                text_chart = alt.Chart(cohort_sizes).mark_text(
                    align='center',
                    baseline='middle',
                    fontSize=12,
                    fontWeight='bold'
                ).encode(
                    x='cohort_year:N',
                    y='y_pos:Q',
                    text='label:N'
                )
               
                # Combine layers
                combined_box_chart = (red_zone + yellow_zone + green_zone + line_62 + line_66 + box_chart + text_chart).resolve_scale(
                    y='shared'
                ).properties(
                    width=600,
                    height=400,
                    title="Score Distribution by Cohort (Aggregated Scores)"
                )
               
                st.altair_chart(combined_box_chart, use_container_width=True)
               
                # Flag distribution from aggregated data
                flag_data = student_aggregated.groupby(['cohort_year', 'flag']).size().reset_index(name='count')
               
            else:
                # Single exam OR (single cohort + single exam) = INDIVIDUAL MODE
                if len(selected_exams) == 1:
                    st.markdown("### 🔍 **Individual Exam Analysis**")
                    st.markdown(f"Detailed analysis for **{selected_exams[0]}**")
                else:
                    st.markdown("### 🔍 **Individual Cohort Analysis**") 
                    st.markdown(f"Detailed analysis for **{selected_cohorts[0]} Cohort**")
               
                # Score distribution by cohort for single exam
                if len(selected_cohorts) > 1:
                    groupby_col = 'cohort_year'
                    chart_x = alt.X('cohort_year:N', title='Cohort Year')
                    title_suffix = f"- {selected_exams[0]}"
                else:
                    groupby_col = 'exam_label'
                    chart_x = alt.X('exam_label:N', title='Exam', axis=alt.Axis(labelAngle=-45))
                    title_suffix = f"- {selected_cohorts[0]} Cohort"
               
                # Enhanced summary with full variability statistics
                summary = cohort_data.groupby(groupby_col).agg({
                    'total_score': ['count', 'mean', 'median', 'std', 'min', 'max', lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
                }).round(1)
               
                summary.columns = ['Sample Size (n)', 'Mean', 'Median', 'Std Dev', 'Min', 'Max', 'Q1 (25%)', 'Q3 (75%)']
                summary['IQR'] = summary['Q3 (75%)'] - summary['Q1 (25%)']
                summary['Range'] = summary['Max'] - summary['Min']
                
                # Add variability classification
                summary['Variability'] = summary['Std Dev'].apply(
                    lambda x: "Low (σ<5)" if x < 5 else "Moderate (5≤σ<10)" if x < 10 else "High (σ≥10)"
                )
                
                st.markdown("**📊 Comprehensive Score Statistics**")
                st.dataframe(summary, use_container_width=True)
               
                # Enhanced box plot of score distributions
                base_chart = alt.Chart(cohort_data)
               
                # Background shaded zones
                red_zone = alt.Chart(pd.DataFrame({'y': [0], 'y2': [62]})).mark_rect(
                    opacity=0.1, color='red'
                ).encode(
                    y=alt.Y('y:Q', scale=alt.Scale(domain=[30, 95])),
                    y2='y2:Q'
                )
               
                yellow_zone = alt.Chart(pd.DataFrame({'y': [62], 'y2': [66]})).mark_rect(
                    opacity=0.1, color='orange'
                ).encode(y='y:Q', y2='y2:Q')
               
                green_zone = alt.Chart(pd.DataFrame({'y': [66], 'y2': [95]})).mark_rect(
                    opacity=0.1, color='green'
                ).encode(y='y:Q', y2='y2:Q')
               
                # Reference lines
                line_62 = alt.Chart(pd.DataFrame({'threshold': [62]})).mark_rule(
                    color='orange', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                line_66 = alt.Chart(pd.DataFrame({'threshold': [66]})).mark_rule(
                    color='green', strokeDash=[5, 5], size=2
                ).encode(y='threshold:Q')
               
                # Enhanced box plot
                box_chart = base_chart.mark_boxplot(
                    size=60,
                    outliers={'color': 'red', 'size': 35}
                ).encode(
                    x=chart_x,
                    y=alt.Y('total_score:Q', title='Total Score', scale=alt.Scale(domain=[30, 95])),
                    color=alt.Color(f'{groupby_col}:N', title=groupby_col.replace('_', ' ').title())
                )
                
                # Add sample size annotations
                size_data = cohort_data.groupby(groupby_col)['total_score'].count().reset_index()
                size_data.columns = [groupby_col, 'count']
                size_data['y_pos'] = 92
                size_data['label'] = 'n=' + size_data['count'].astype(str)
                
                text_chart = alt.Chart(size_data).mark_text(
                    align='center',
                    baseline='middle',
                    fontSize=12,
                    fontWeight='bold'
                ).encode(
                    x=f'{groupby_col}:N',
                    y='y_pos:Q',
                    text='label:N'
                )
               
                # Combine layers
                combined_box_chart = (red_zone + yellow_zone + green_zone + line_62 + line_66 + box_chart + text_chart).resolve_scale(
                    y='shared'
                ).properties(
                    width=600,
                    height=400,
                    title=f"Score Distribution {title_suffix}"
                )
               
                st.altair_chart(combined_box_chart, use_container_width=True)
               
                # Flag distribution
                flag_data = cohort_data.groupby([groupby_col, 'flag']).size().reset_index(name='count')
           
            # Show flag distribution chart (works for all modes)
            st.subheader("📊 Step 1 Readiness Distribution")
           
            # Determine grouping for flag chart
            if len(selected_cohorts) == 1 and len(selected_exams) > 1:
                groupby_col = 'exam_label'
                chart_x = alt.X('exam_label:N', title='Exam', axis=alt.Axis(labelAngle=-45))
            elif len(selected_cohorts) > 1 and len(selected_exams) > 1:
                groupby_col = 'cohort_year'
                chart_x = alt.X('cohort_year:N', title='Cohort Year')
                flag_data = student_aggregated.groupby(['cohort_year', 'flag']).size().reset_index(name='count')
            elif len(selected_cohorts) > 1:
                groupby_col = 'cohort_year'
                chart_x = alt.X('cohort_year:N', title='Cohort Year')
            else:
                groupby_col = 'exam_label'
                chart_x = alt.X('exam_label:N', title='Exam', axis=alt.Axis(labelAngle=-45))
           
            flag_data['percentage'] = flag_data.groupby(groupby_col)['count'].transform(lambda x: 100 * x / x.sum())
           
            # Add readiness labels for display
            flag_data['readiness_status'] = flag_data['flag'].apply(get_readiness_status)
           
            flag_chart = alt.Chart(flag_data).mark_bar().encode(
                x=chart_x,
                y=alt.Y('percentage:Q', title='Percentage of Students'),
                color=alt.Color('flag:N',
                               scale=alt.Scale(domain=['Green', 'Yellow', 'Red'],
                                             range=['#28a745', '#ffc107', '#dc3545']),
                               legend=alt.Legend(title="Step 1 Readiness",
                                               labelExpr="datum.value == 'Green' ? 'Step 1 Ready' : datum.value == 'Yellow' ? 'Approaching Readiness' : 'Below Threshold'")),
                tooltip=[groupby_col, 'readiness_status:N', 'count', 'percentage:Q']
            ).properties(width=500, height=300, title="Step 1 Readiness Distribution")
            st.altair_chart(flag_chart, use_container_width=True)
           
            # Enhanced psychometric explanation
            st.markdown("""
            **📊 Psychometric Interpretation Guide:**
            - 🟢 **Green Zone (66+)**: Step 1 Ready - students on track for success
            - 🟡 **Yellow Zone (62-65)**: Approaching Readiness - monitor and support  
            - 🔴 **Red Zone (<62)**: Below Readiness Threshold - immediate intervention needed
            - **Sample Size (n)**: Critical for interpretation - larger samples provide more reliable estimates
            - **Standard Deviation (σ)**: Key variability metric - higher values indicate more diverse performance
            - **IQR (Interquartile Range)**: Shows spread of middle 50% of students
            """)

            # 🎯 NEW FEATURE: Enhanced Temporal Risk Flag Analysis
            st.subheader("📈 Risk Flag Distribution Trends Over Time")
            st.info("💡 **Psychometric Insight**: Track how readiness categories shift across exam periods. Essential for identifying curriculum effectiveness and intervention timing.")
            
            # Check if we have temporal data (multiple exam rounds)
            if 'exam_round' in cohort_data.columns and len(cohort_data['exam_round'].unique()) > 1:
                # Create temporal flag analysis
                temporal_flag_data = cohort_data.groupby(['exam_round', 'flag']).size().reset_index(name='count')
                
                # Add exam round ordering for proper time sequence
                exam_round_order = {'Spring MS1': 1, 'Fall MS2': 2, 'Spring MS2': 3}
                temporal_flag_data['exam_order'] = temporal_flag_data['exam_round'].map(exam_round_order)
                temporal_flag_data = temporal_flag_data.sort_values('exam_order')
                
                # Calculate percentages by exam round
                temporal_flag_data['percentage'] = temporal_flag_data.groupby('exam_round')['count'].transform(lambda x: 100 * x / x.sum())
                
                # Add readiness labels
                temporal_flag_data['readiness_status'] = temporal_flag_data['flag'].apply(get_readiness_status)
                
                # Add total students per exam round for context
                exam_totals = cohort_data.groupby('exam_round').size().reset_index(name='total_students')
                exam_totals['exam_order'] = exam_totals['exam_round'].map(exam_round_order)
                temporal_flag_data = temporal_flag_data.merge(exam_totals[['exam_round', 'total_students']], on='exam_round')
                
                # Create enhanced trend visualization with multiple chart types
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📊 Readiness Trend Lines**")
                    
                    # Line chart showing percentage trends
                    line_chart = alt.Chart(temporal_flag_data).mark_line(
                        point=True, 
                        strokeWidth=3
                    ).encode(
                        x=alt.X('exam_order:O', 
                               title='Exam Period',
                               axis=alt.Axis(labelExpr="datum.value == 1 ? 'Spring MS1' : datum.value == 2 ? 'Fall MS2' : 'Spring MS2'")),
                        y=alt.Y('percentage:Q', 
                               title='Percentage of Students',
                               scale=alt.Scale(domain=[0, 100])),
                        color=alt.Color('flag:N',
                                       scale=alt.Scale(domain=['Green', 'Yellow', 'Red'],
                                                     range=['#28a745', '#ffc107', '#dc3545']),
                                       legend=alt.Legend(title="Step 1 Readiness",
                                                       labelExpr="datum.value == 'Green' ? 'Step 1 Ready' : datum.value == 'Yellow' ? 'Approaching Readiness' : 'Below Threshold'")),
                        tooltip=['exam_round:N', 'readiness_status:N', 'percentage:Q', 'count:Q', 'total_students:Q']
                    ).properties(
                        height=300,
                        title="Readiness Category Trends Across Time"
                    )
                    
                    st.altair_chart(line_chart, use_container_width=True)
                
                with col2:
                    st.markdown("**📈 Stacked Area Progression**")
                    
                    # Stacked area chart showing composition over time
                    area_chart = alt.Chart(temporal_flag_data).mark_area(
                        opacity=0.7
                    ).encode(
                        x=alt.X('exam_order:O',
                               title='Exam Period',
                               axis=alt.Axis(labelExpr="datum.value == 1 ? 'Spring MS1' : datum.value == 2 ? 'Fall MS2' : 'Spring MS2'")),
                        y=alt.Y('percentage:Q',
                               title='Cumulative Percentage',
                               stack='zero'),
                        color=alt.Color('flag:N',
                                       scale=alt.Scale(domain=['Red', 'Yellow', 'Green'],  # Red at bottom
                                                     range=['#dc3545', '#ffc107', '#28a745']),
                                       legend=alt.Legend(title="Step 1 Readiness",
                                                       labelExpr="datum.value == 'Green' ? 'Step 1 Ready' : datum.value == 'Yellow' ? 'Approaching Readiness' : 'Below Threshold'")),
                        order=alt.Order('flag:N', sort='descending'),  # Red at bottom, Green at top
                        tooltip=['exam_round:N', 'readiness_status:N', 'percentage:Q', 'count:Q', 'total_students:Q']
                    ).properties(
                        height=300,
                        title="Cumulative Readiness Distribution"
                    )
                    
                    st.altair_chart(area_chart, use_container_width=True)
                
                # Detailed trend analysis table
                st.markdown("**📋 Detailed Trend Analysis**")
                
                # Pivot the data for better display
                trend_pivot = temporal_flag_data.pivot(index=['exam_round', 'exam_order', 'total_students'], 
                                                      columns='flag', 
                                                      values=['count', 'percentage']).round(1)
                
                # Flatten column names
                trend_pivot.columns = [f'{flag}_{metric}' for metric, flag in trend_pivot.columns]
                trend_pivot = trend_pivot.reset_index()
                
                # Reorder columns for readability
                display_columns = ['exam_round', 'total_students']
                for flag in ['Red', 'Yellow', 'Green']:
                    if f'{flag}_count' in trend_pivot.columns:
                        display_columns.extend([f'{flag}_count', f'{flag}_percentage'])
                
                trend_display = trend_pivot[display_columns].copy()
                
                # Rename columns for better presentation
                column_renames = {
                    'exam_round': 'Exam Period',
                    'total_students': 'Total Students (n)',
                    'Red_count': '🚨 Below Threshold (n)',
                    'Red_percentage': '🚨 Below Threshold (%)',
                    'Yellow_count': '⚠️ Approaching (n)', 
                    'Yellow_percentage': '⚠️ Approaching (%)',
                    'Green_count': '✅ Step 1 Ready (n)',
                    'Green_percentage': '✅ Step 1 Ready (%)'
                }
                
                trend_display = trend_display.rename(columns={k: v for k, v in column_renames.items() if k in trend_display.columns})
                
                # Format percentage columns
                for col in trend_display.columns:
                    if '(%)' in col:
                        trend_display[col] = trend_display[col].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "0%")
                
                st.dataframe(trend_display, use_container_width=True)
                
                # Key insights from temporal analysis
                st.markdown("**🎯 Temporal Insights**")
                
                # Calculate key metrics for insights
                if len(temporal_flag_data) >= 6:  # Need data for all flag types across periods
                    try:
                        # Get first and last time periods
                        first_period = temporal_flag_data[temporal_flag_data['exam_order'] == temporal_flag_data['exam_order'].min()]
                        last_period = temporal_flag_data[temporal_flag_data['exam_order'] == temporal_flag_data['exam_order'].max()]
                        
                        # Calculate changes in each category
                        insights = []
                        
                        for flag in ['Red', 'Yellow', 'Green']:
                            first_pct = first_period[first_period['flag'] == flag]['percentage'].iloc[0] if not first_period[first_period['flag'] == flag].empty else 0
                            last_pct = last_period[last_period['flag'] == flag]['percentage'].iloc[0] if not last_period[last_period['flag'] == flag].empty else 0
                            change = last_pct - first_pct
                            
                            flag_name = get_readiness_status(flag)
                            
                            if abs(change) >= 5:  # Significant change threshold
                                if change > 0:
                                    trend_direction = "📈 **Increased**"
                                    if flag == 'Green':
                                        insights.append(f"🎯 **Positive Trend**: {flag_name} students {trend_direction} by {change:+.1f}% from MS1 to MS2")
                                    else:
                                        insights.append(f"⚠️ **Concerning Trend**: {flag_name} students {trend_direction} by {change:+.1f}% from MS1 to MS2")
                                else:
                                    trend_direction = "📉 **Decreased**"
                                    if flag == 'Green':
                                        insights.append(f"⚠️ **Concerning Trend**: {flag_name} students {trend_direction} by {change:+.1f}% from MS1 to MS2")
                                    else:
                                        insights.append(f"🎯 **Positive Trend**: {flag_name} students {trend_direction} by {change:+.1f}% from MS1 to MS2")
                        
                        # Show insights
                        if insights:
                            for insight in insights:
                                st.markdown(insight)
                        else:
                            st.info("📊 **Stable Patterns**: Readiness distributions show minimal change over time (±5%)")
                            
                        # Sample size warnings
                        min_sample = exam_totals['total_students'].min()
                        if min_sample < 30:
                            st.warning(f"⚠️ **Small Sample Alert**: Minimum n={min_sample} students in some periods. Interpret trends cautiously.")
                        
                    except Exception as e:
                        st.info("📊 Trend analysis requires data from multiple time periods.")
                
                # Log temporal analysis interaction
                log_feature_interaction(current_user, "temporal_risk_flag_analysis", {
                    "cohorts_analyzed": selected_cohorts,
                    "exams_analyzed": selected_exams,
                    "num_time_periods": len(temporal_flag_data['exam_round'].unique()),
                    "total_students_analyzed": cohort_data['student_id'].nunique(),
                    "analysis_type": "cohort_level_temporal_flags"
                })
                
            elif 'exam_date' in cohort_data.columns and len(cohort_data['exam_date'].unique()) > 1:
                # Fallback to date-based analysis if exam_round not available
                st.info("📅 **Date-based Analysis**: Showing flag distribution by exam dates (exam round data not available)")
                
                # Convert exam_date to datetime for proper sorting
                cohort_data['exam_datetime'] = pd.to_datetime(cohort_data['exam_date'])
                
                # Group by exam date and flag
                date_flag_data = cohort_data.groupby(['exam_date', 'flag']).size().reset_index(name='count')
                date_flag_data['exam_datetime'] = pd.to_datetime(date_flag_data['exam_date'])
                date_flag_data = date_flag_data.sort_values('exam_datetime')
                
                # Calculate percentages by date
                date_flag_data['percentage'] = date_flag_data.groupby('exam_date')['count'].transform(lambda x: 100 * x / x.sum())
                date_flag_data['readiness_status'] = date_flag_data['flag'].apply(get_readiness_status)
                
                # Simple line chart by date
                date_line_chart = alt.Chart(date_flag_data).mark_line(
                    point=True,
                    strokeWidth=3
                ).encode(
                    x=alt.X('exam_datetime:T', title='Exam Date'),
                    y=alt.Y('percentage:Q', title='Percentage of Students', scale=alt.Scale(domain=[0, 100])),
                    color=alt.Color('flag:N',
                                   scale=alt.Scale(domain=['Green', 'Yellow', 'Red'],
                                                 range=['#28a745', '#ffc107', '#dc3545']),
                                   legend=alt.Legend(title="Step 1 Readiness")),
                    tooltip=['exam_date:N', 'readiness_status:N', 'percentage:Q', 'count:Q']
                ).properties(
                    height=350,
                    title="Readiness Distribution Trends by Date"
                )
                
                st.altair_chart(date_line_chart, use_container_width=True)
                
            else:
                st.info("📊 **Single Time Point**: Temporal trend analysis requires multiple exam periods or dates. Select exams from different time periods to see trends.")
                st.markdown("**💡 Tip**: Try selecting both MS1 and MS2 exams to see learning progression patterns.")

            # Log enhanced chart interactions
            log_feature_interaction(current_user, "enhanced_cohort_analysis_charts", {
                "num_cohorts": len(selected_cohorts),
                "num_exams": len(selected_exams),
                "analysis_mode": "comparison" if len(selected_cohorts) == 1 and len(selected_exams) > 1 else "aggregated" if len(selected_cohorts) > 1 and len(selected_exams) > 1 else "individual",
                "psychometric_enhancements": "box_plots_with_variability_focus"
            })
           
            # Content Area Analysis (if EPC data available) - Simplified for space
            if not epc_scores.empty:
                st.subheader("📚 Content Area Performance by Cohort")
               
                # Merge EPC data with cohort info
                epc_cohort = epc_scores.merge(students[['student_id', 'cohort_year']], on='student_id')
                epc_cohort = epc_cohort[epc_cohort['cohort_year'].isin(selected_cohorts)].copy()
               
                # Filter by selected exams for EPC data using the same logic
                if 'exam_round' in epc_cohort.columns:
                    epc_cohort['exam_label'] = epc_cohort['exam_type'] + " - " + epc_cohort['exam_round'].astype(str).str.replace('MS', 'ME')
                else:
                    epc_cohort['exam_label'] = epc_cohort['exam_type']
               
                epc_cohort = epc_cohort[epc_cohort['exam_label'].isin(selected_exams)].copy()
               
                # Identify EPC content area columns more precisely
                exclude_cols_epc = ['student_id', 'exam_type', 'exam_date', 'cohort_year', 'exam_label', 'exam_round']
                epc_cols = [col for col in epc_cohort.columns if col not in exclude_cols_epc]
               
                if epc_cols and not epc_cohort.empty:
                    # Melt EPC data for analysis
                    id_vars = ['student_id', 'cohort_year', 'exam_type', 'exam_date', 'exam_label']
                    if 'exam_round' in epc_cohort.columns:
                        id_vars.append('exam_round')
                   
                    epc_long = epc_cohort.melt(
                        id_vars=id_vars,
                        value_vars=epc_cols,
                        var_name='Content_Area',
                        value_name='Score'
                    )
                   
                    # Convert to numeric and clean
                    epc_long["Score"] = pd.to_numeric(epc_long["Score"], errors='coerce')
                    epc_long = epc_long.dropna(subset=["Score"]).copy()
                   
                    if not epc_long.empty:
                        # Show top weakest areas
                        if len(selected_cohorts) > 1:
                            content_avg = epc_long.groupby(['cohort_year', 'Content_Area'])['Score'].mean().reset_index()
                            st.markdown("**Weakest Content Areas by Cohort:**")
                            for cohort in selected_cohorts:
                                cohort_weak = content_avg[content_avg['cohort_year'] == cohort].nsmallest(3, 'Score')
                                if not cohort_weak.empty:
                                    st.markdown(f"**{cohort} Cohort:**")
                                    for _, row in cohort_weak.iterrows():
                                        st.markdown(f"  - {row['Content_Area']}: {row['Score']:.1f}%")
                        else:
                            # Single cohort
                            content_avg = epc_long.groupby('Content_Area')['Score'].mean().reset_index()
                            content_avg = content_avg.sort_values('Score', ascending=True)
                           
                            st.markdown("**Weakest Content Areas:**")
                            for _, row in content_avg.head(5).iterrows():
                                st.markdown(f"  - {row['Content_Area']}: {row['Score']:.1f}%")
                               
                        # Log content area analysis
                        log_feature_interaction(current_user, "content_area_analysis", {
                            "num_content_areas": len(epc_long["Content_Area"].unique()),
                            "cohorts_analyzed": selected_cohorts,
                            "exams_analyzed": selected_exams
                        })
                    else:
                        st.warning("No valid EPC scores found after data cleaning.")
                else:
                    st.warning("No content area columns found in EPC data.")
            else:
                st.info("EPC data not available for content area analysis.")

            # Question-Level Content Analysis (QLF) - Cohort Level
            # Note: QLF data is only available for CBSE exams, not CBSSA
            if not qlf_responses.empty:
                st.subheader("🔍 Question-Level Content Analysis (QLF)")
                st.markdown("*Institutional performance patterns by content area*")
               
                # Check if any CBSE exams are selected (QLF only exists for CBSE)
                cbse_exams_selected = [exam for exam in selected_exams if 'CBSE' in exam]
               
                if not cbse_exams_selected:
                    st.info("📝 **QLF Analysis Not Available**: Question-level feedback data is only available for CBSE exams. Please select at least one CBSE exam to view QLF analysis.")
                    st.markdown("**Selected exams:** " + ", ".join(selected_exams))
                    st.markdown("**Available for QLF:** CBSE exams only")
                else:
                    # Check if QLF data already has cohort_year or needs merge
                    try:
                        if 'cohort_year' in qlf_responses.columns:
                            # QLF data already has cohort info, use it directly
                            qlf_cohort = qlf_responses.copy()
                        else:
                            # Need to merge with students data
                            qlf_cohort = qlf_responses.merge(students[['student_id', 'cohort_year']], on='student_id', how='inner')
                       
                        # Check if we have cohort data
                        if qlf_cohort.empty or 'cohort_year' not in qlf_cohort.columns:
                            st.warning("⚠️ **No QLF data available** for the selected cohorts. This could mean:")
                            st.markdown("- No students in selected cohorts have taken CBSE exams with QLF data")
                            st.markdown("- Data synchronization issue between student records and QLF responses")
                        else:
                            # Filter by selected cohorts
                            qlf_cohort = qlf_cohort[qlf_cohort['cohort_year'].isin(selected_cohorts)].copy()
                           
                            # Filter by selected exams for QLF data (only CBSE exams)
                            if 'exam_round' in qlf_cohort.columns:
                                qlf_cohort['exam_label'] = qlf_cohort['exam_type'] + " - " + qlf_cohort['exam_round'].astype(str).str.replace('MS', 'ME')
                            else:
                                qlf_cohort['exam_label'] = qlf_cohort['exam_type']
                           
                            # Only include CBSE exams that are in the selected list
                            qlf_cohort = qlf_cohort[qlf_cohort['exam_label'].isin(cbse_exams_selected)].copy()
                           
                            # Check if we have data after filtering
                            if qlf_cohort.empty:
                                st.info(f"📝 **No QLF data available** for the selected CBSE exams: {', '.join(cbse_exams_selected)}")
                                st.markdown("**Note:** QLF analysis requires CBSE exam data for the selected cohorts.")
                            else:
                                # Clean and validate data
                                qlf_cohort["correct"] = pd.to_numeric(qlf_cohort["correct"], errors='coerce')
                                qlf_cohort["national_pct_correct"] = pd.to_numeric(qlf_cohort["national_pct_correct"], errors='coerce')
                                qlf_cohort_clean = qlf_cohort.dropna(subset=["correct", "physician_competency", "content_topic", "content_description", "national_pct_correct"]).copy()
                               
                                if not qlf_cohort_clean.empty:
                                    # Summary metrics
                                    col1, col2, col3, col4 = st.columns(4)
                                   
                                    total_responses = len(qlf_cohort_clean)
                                    unique_topics = qlf_cohort_clean['content_description'].nunique()
                                    overall_cohort_pct = (qlf_cohort_clean['correct'].sum() / total_responses) * 100
                                    avg_national_pct = qlf_cohort_clean['national_pct_correct'].mean()
                                   
                                    with col1:
                                        st.metric("Total Responses", f"{total_responses:,}")
                                    with col2:
                                        st.metric("Unique Topics", unique_topics)
                                    with col3:
                                        st.metric("Cohort Performance", f"{overall_cohort_pct:.1f}%")
                                    with col4:
                                        performance_gap = overall_cohort_pct - avg_national_pct
                                        st.metric("vs National Avg", f"{performance_gap:+.1f}%",
                                                delta=f"{performance_gap:.1f}%")
                                   
                                    # Filtering options
                                    st.markdown("---")
                                    col1, col2, col3 = st.columns(3)
                                   
                                    with col1:
                                        qlf_competency_filter = st.selectbox(
                                            "Physician Competency",
                                            ["All"] + sorted(qlf_cohort_clean["physician_competency"].unique()),
                                            help="Filter by competency area",
                                            key="cohort_qlf_competency"
                                        )
                                   
                                    with col2:
                                        qlf_topic_filter = st.selectbox(
                                            "Content Topic",
                                            ["All"] + sorted(qlf_cohort_clean["content_topic"].unique()),
                                            help="Filter by content topic",
                                            key="cohort_qlf_topic"
                                        )
                                   
                                    with col3:
                                        performance_filter = st.selectbox(
                                            "Performance Level",
                                            ["All", "Below National Average", "Above National Average", "Significant Gaps (>10% below)"],
                                            help="Filter by performance vs national",
                                            key="cohort_qlf_performance"
                                        )
                                   
                                    # Apply filters
                                    filtered_qlf_cohort = qlf_cohort_clean.copy()
                                   
                                    if qlf_competency_filter != "All":
                                        filtered_qlf_cohort = filtered_qlf_cohort[filtered_qlf_cohort["physician_competency"] == qlf_competency_filter]
                                   
                                    if qlf_topic_filter != "All":
                                        filtered_qlf_cohort = filtered_qlf_cohort[filtered_qlf_cohort["content_topic"] == qlf_topic_filter]
                                   
                                    # Aggregate by content description
                                    if not filtered_qlf_cohort.empty:
                                        content_analysis = filtered_qlf_cohort.groupby(['physician_competency', 'content_topic', 'content_description']).agg({
                                            'correct': ['count', 'sum'],
                                            'national_pct_correct': 'first'  # National % should be same for all instances
                                        }).round(1)
                                       
                                        content_analysis.columns = ['Total_Responses', 'Correct_Responses', 'National_Pct']
                                        content_analysis['Cohort_Pct'] = (content_analysis['Correct_Responses'] / content_analysis['Total_Responses']) * 100
                                        content_analysis['Performance_Gap'] = content_analysis['Cohort_Pct'] - content_analysis['National_Pct']
                                        content_analysis = content_analysis.round(1)
                                       
                                        # Add risk level
                                        def get_risk_level(gap, cohort_pct):
                                            if gap <= -15:
                                                return "🚨 Critical Gap"
                                            elif gap <= -10:
                                                return "⚠️ Significant Gap"
                                            elif gap <= -5:
                                                return "⚡ Moderate Gap"
                                            elif gap >= 10:
                                                return "🌟 Strong Performance"
                                            elif gap >= 5:
                                                return "✅ Above Average"
                                            else:
                                                return "➖ Near National"
                                       
                                        content_analysis['Risk_Level'] = content_analysis.apply(
                                            lambda row: get_risk_level(row['Performance_Gap'], row['Cohort_Pct']), axis=1
                                        )
                                       
                                        # Apply performance filter
                                        if performance_filter == "Below National Average":
                                            content_analysis = content_analysis[content_analysis['Performance_Gap'] < 0]
                                        elif performance_filter == "Above National Average":
                                            content_analysis = content_analysis[content_analysis['Performance_Gap'] > 0]
                                        elif performance_filter == "Significant Gaps (>10% below)":
                                            content_analysis = content_analysis[content_analysis['Performance_Gap'] <= -10]
                                       
                                        # Reset index to make hierarchical columns accessible
                                        content_analysis = content_analysis.reset_index()
                                       
                                        # Sort by performance gap (worst first)
                                        content_analysis = content_analysis.sort_values('Performance_Gap')
                                       
                                        # Display results
                                        if not content_analysis.empty:
                                            st.markdown(f"**Showing {len(content_analysis)} content areas** (filtered from {unique_topics} total)")
                                           
                                            # Create display version
                                            display_content = content_analysis.copy()
                                            display_content['Students_Tested'] = display_content['Total_Responses']
                                            display_content['Cohort_%'] = display_content['Cohort_Pct'].apply(lambda x: f"{x:.1f}%")
                                            display_content['National_%'] = display_content['National_Pct'].apply(lambda x: f"{x:.1f}%")
                                            display_content['Gap'] = display_content['Performance_Gap'].apply(lambda x: f"{x:+.1f}%")
                                           
                                            # Select display columns
                                            final_display_content = display_content[[
                                                'physician_competency', 'content_topic', 'content_description',
                                                'Students_Tested', 'Cohort_%', 'National_%', 'Gap', 'Risk_Level'
                                            ]].copy()
                                           
                                            final_display_content = final_display_content.rename(columns={
                                                'physician_competency': 'Physician Competency',
                                                'content_topic': 'Content Topic',
                                                'content_description': 'Content Description',
                                                'Risk_Level': 'Performance Level'
                                            })
                                           
                                            # Style the dataframe
                                            def highlight_performance_gap(row):
                                                colors = []
                                                for col in row.index:
                                                    if col == 'Gap':
                                                        gap_val = float(row[col].replace('%', '').replace('+', ''))
                                                        if gap_val <= -15:
                                                            colors.append('background-color: #dc3545; color: white; font-weight: bold')  # Critical
                                                        elif gap_val <= -10:
                                                            colors.append('background-color: #fd7e14; color: white; font-weight: bold')  # Significant
                                                        elif gap_val <= -5:
                                                            colors.append('background-color: #ffc107; color: black; font-weight: bold')  # Moderate
                                                        elif gap_val >= 10:
                                                            colors.append('background-color: #198754; color: white; font-weight: bold')  # Strong
                                                        elif gap_val >= 5:
                                                            colors.append('background-color: #20c997; color: white; font-weight: bold')  # Above
                                                        else:
                                                            colors.append('background-color: #6c757d; color: white')  # Near national
                                                    elif col == 'Performance Level':
                                                        if '🚨' in str(row[col]):
                                                            colors.append('background-color: #f8d7da; color: #721c24; font-weight: bold')
                                                        elif '⚠️' in str(row[col]):
                                                            colors.append('background-color: #fff3cd; color: #856404; font-weight: bold')
                                                        elif '🌟' in str(row[col]) or '✅' in str(row[col]):
                                                            colors.append('background-color: #d4edda; color: #155724; font-weight: bold')
                                                        else:
                                                            colors.append('')
                                                    else:
                                                        colors.append('')
                                                return colors
                                           
                                            styled_content = final_display_content.style.apply(highlight_performance_gap, axis=1)
                                            st.dataframe(styled_content, use_container_width=True, height=400)
                                           
                                            # Key insights summary
                                            st.markdown("---")
                                            st.markdown("### 🎯 Institutional Insights")
                                           
                                            col1, col2 = st.columns(2)
                                           
                                            with col1:
                                                st.markdown("**🚨 Priority Areas for Curriculum Focus:**")
                                                critical_gaps = content_analysis[content_analysis['Performance_Gap'] <= -10].head(5)
                                                if not critical_gaps.empty:
                                                    for _, row in critical_gaps.iterrows():
                                                        gap = row['Performance_Gap']
                                                        emoji = "🚨" if gap <= -15 else "⚠️"
                                                        st.markdown(f"{emoji} **{row['content_topic']}**: {row['content_description'][:40]}... ({gap:+.1f}%)")
                                                else:
                                                    st.success("🎉 No critical content gaps identified!")
                                           
                                            with col2:
                                                st.markdown("**🌟 Institutional Strengths:**")
                                                strengths = content_analysis[content_analysis['Performance_Gap'] >= 5].head(5)
                                                if not strengths.empty:
                                                    for _, row in strengths.iterrows():
                                                        gap = row['Performance_Gap']
                                                        emoji = "🌟" if gap >= 10 else "✅"
                                                        st.markdown(f"{emoji} **{row['content_topic']}**: {row['content_description'][:40]}... ({gap:+.1f}%)")
                                                else:
                                                    st.info("Focus on maintaining current performance levels.")
                                           
                                            # Competency-level summary
                                            st.markdown("**📊 Performance by Physician Competency:**")
                                            competency_summary = filtered_qlf_cohort.groupby('physician_competency').agg({
                                                'correct': ['count', 'sum'],
                                                'national_pct_correct': 'mean'
                                            })
                                            competency_summary.columns = ['Total', 'Correct', 'Avg_National']
                                            competency_summary['Cohort_Pct'] = (competency_summary['Correct'] / competency_summary['Total']) * 100
                                            competency_summary['Gap'] = competency_summary['Cohort_Pct'] - competency_summary['Avg_National']
                                           
                                            for comp, row in competency_summary.iterrows():
                                                gap = row['Gap']
                                                if gap <= -10:
                                                    emoji = "🚨"
                                                elif gap <= -5:
                                                    emoji = "⚠️"
                                                elif gap >= 5:
                                                    emoji = "✅"
                                                else:
                                                    emoji = "➖"
                                                st.markdown(f"{emoji} **{comp}**: {row['Cohort_Pct']:.1f}% cohort vs {row['Avg_National']:.1f}% national ({gap:+.1f}%)")
                                           
                                            # Log cohort QLF interaction
                                            log_feature_interaction(current_user, "cohort_qlf_analysis", {
                                                "cohorts_analyzed": selected_cohorts,
                                                "exams_analyzed": selected_exams,
                                                "total_responses": total_responses,
                                                "content_areas_analyzed": len(content_analysis),
                                                "critical_gaps": len(content_analysis[content_analysis['Performance_Gap'] <= -15]),
                                                "significant_gaps": len(content_analysis[content_analysis['Performance_Gap'] <= -10]),
                                                "strengths": len(content_analysis[content_analysis['Performance_Gap'] >= 10]),
                                                "overall_performance_gap": performance_gap,
                                                "competency_filter": qlf_competency_filter,
                                                "topic_filter": qlf_topic_filter,
                                                "performance_filter": performance_filter
                                            })
                                           
                                        else:
                                            st.info("No content areas match the selected filters. Try adjusting your filter criteria.")
                                    else:
                                        st.warning("No valid QLF data found after applying content area filters.")
                                else:
                                    st.warning("No valid QLF data found for the selected cohorts and CBSE exams after data cleaning.")
                   
                    except Exception as e:
                        st.error(f"Error processing QLF data: {str(e)}")
                        st.info("📝 **QLF data unavailable** - this feature requires CBSE exam data with student enrollment information.")
            else:
                st.info("📝 **QLF Analysis Not Available**: No question-level feedback data found. QLF analysis requires CBSE exam data.")

            # NEW FEATURE: Content Area Learning Trajectories
            if not qlf_responses.empty:
                st.subheader("📈 Content Area Learning Trajectories")
                st.markdown("*Track how student mastery evolves across medical school timeline*")
                
                # Better Value Proposition
                st.info("📊 **Discover Curriculum Effectiveness**: See how students progress from MS1 to MS2 on specific medical topics. Perfect for curriculum committees, identifying teaching gaps, and accreditation evidence.")
                
                # Check if any CBSE exams are selected (QLF only exists for CBSE)
                cbse_exams_selected = [exam for exam in selected_exams if 'CBSE' in exam]
                
                if not cbse_exams_selected:
                    st.info("📝 **Trajectory Analysis Not Available**: Learning trajectory analysis requires CBSE exam data. Please select at least one CBSE exam.")
                else:
                    # Check if QLF data already has cohort_year or needs merge
                    try:
                        if 'cohort_year' in qlf_responses.columns:
                            # QLF data already has cohort info, use it directly
                            trajectory_qlf = qlf_responses.copy()
                        else:
                            # Need to merge with students data
                            trajectory_qlf = qlf_responses.merge(students[['student_id', 'cohort_year']], on='student_id', how='inner')
                        
                        if not trajectory_qlf.empty and 'cohort_year' in trajectory_qlf.columns:
                            # Filter by selected cohorts
                            trajectory_qlf = trajectory_qlf[trajectory_qlf['cohort_year'].isin(selected_cohorts)].copy()
                            
                            # Add exam labels
                            if 'exam_round' in trajectory_qlf.columns:
                                trajectory_qlf['exam_label'] = trajectory_qlf['exam_type'] + " - " + trajectory_qlf['exam_round'].astype(str).str.replace('MS', 'ME')
                            else:
                                trajectory_qlf['exam_label'] = trajectory_qlf['exam_type']
                            
                            # Filter by CBSE exams in selection
                            trajectory_qlf = trajectory_qlf[trajectory_qlf['exam_label'].isin(cbse_exams_selected)].copy()
                            
                            if not trajectory_qlf.empty:
                                # Clean data
                                trajectory_qlf["correct"] = pd.to_numeric(trajectory_qlf["correct"], errors='coerce')
                                trajectory_qlf["national_pct_correct"] = pd.to_numeric(trajectory_qlf["national_pct_correct"], errors='coerce')
                                trajectory_qlf_clean = trajectory_qlf.dropna(subset=["correct", "content_description", "national_pct_correct"]).copy()
                                
                                if not trajectory_qlf_clean.empty:
                                    # Multi-Cohort Warning
                                    if len(selected_cohorts) > 1:
                                        cohort_list = ", ".join(str(c) for c in selected_cohorts)
                                        st.warning(f"📊 **Multi-Cohort Analysis**: Showing COMBINED trajectory across {len(selected_cohorts)} cohorts ({cohort_list}). Data is aggregated across all selected cohorts. Select a single cohort to see individual progression patterns.")
                                    
                                    # Featured Content Areas
                                    available_content_areas = sorted(trajectory_qlf_clean['content_description'].unique())
                                    
                                    st.markdown("### 🌟 Featured Content Areas")
                                    st.markdown("**👋 First time? Try these popular trajectories that often show interesting patterns:**")
                                    
                                    # Define featured areas (pick ones likely to exist in the data)
                                    featured_areas = [
                                        "Immunologic and inflammatory disorders",
                                        "Ischemic heart disease", 
                                        "Diabetes mellitus",
                                        "Obstructive airway disease",
                                        "Viral infections"
                                    ]
                                    
                                    # Filter featured areas to only those that exist in data
                                    existing_featured = [area for area in featured_areas if any(area.lower() in content.lower() for content in available_content_areas)]
                                    
                                    # Show featured areas as buttons or selectbox options
                                    if existing_featured:
                                        col1, col2 = st.columns([2, 1])
                                        with col1:
                                            featured_selection = st.selectbox(
                                                "Quick Start - Choose a Featured Area:",
                                                [""] + existing_featured,
                                                help="These areas typically show clear learning progression patterns"
                                            )
                                        with col2:
                                            st.markdown("**💡 Tips:**")
                                            st.markdown("• Look for topics with curriculum changes")
                                            st.markdown("• Check areas students struggle with")
                                            st.markdown("• Compare vs. national benchmarks")
                                    
                                    # Full content area selection
                                    st.markdown("### 📋 Choose from All Content Areas")
                                    
                                    # Determine default for full dropdown
                                    default_selection = None
                                    if 'featured_selection' in locals() and featured_selection:
                                        # Find the exact match in available areas for the featured selection
                                        exact_match = next((area for area in available_content_areas if featured_selection.lower() in area.lower()), None)
                                        if exact_match:
                                            default_index = available_content_areas.index(exact_match)
                                            default_selection = exact_match
                                            st.success(f"✅ **Featured Area Selected**: {exact_match}")
                                    
                                    # Always show the full dropdown
                                    selected_content_area = st.selectbox(
                                        f"Select from all {len(available_content_areas)} content areas:",
                                        available_content_areas,
                                        index=available_content_areas.index(default_selection) if default_selection else 0,
                                        help="Choose any content area to analyze - you can always change your selection"
                                    )
                                    
                                    if selected_content_area:
                                        # Filter for selected content area
                                        content_trajectory = trajectory_qlf_clean[
                                            trajectory_qlf_clean['content_description'] == selected_content_area
                                        ].copy()
                                        
                                        if not content_trajectory.empty:
                                            # Calculate performance by exam round
                                            trajectory_summary = content_trajectory.groupby('exam_round').agg({
                                                'correct': ['count', 'sum'],
                                                'national_pct_correct': 'first'  # Should be same for all instances
                                            }).round(1)
                                            
                                            trajectory_summary.columns = ['Total_Students', 'Correct_Responses', 'National_Pct']
                                            trajectory_summary['Cohort_Pct'] = (trajectory_summary['Correct_Responses'] / trajectory_summary['Total_Students']) * 100
                                            trajectory_summary['Gap_vs_National'] = trajectory_summary['Cohort_Pct'] - trajectory_summary['National_Pct']
                                            trajectory_summary = trajectory_summary.round(1)
                                            
                                            # Reset index to access exam_round as column
                                            trajectory_summary = trajectory_summary.reset_index()
                                            
                                            # Create exam round order for proper sorting
                                            exam_round_order = {'Spring MS1': 1, 'Fall MS2': 2, 'Spring MS2': 3}
                                            trajectory_summary['exam_order'] = trajectory_summary['exam_round'].map(exam_round_order)
                                            trajectory_summary = trajectory_summary.sort_values('exam_order')
                                            
                                            # Display trajectory table with better context
                                            if len(selected_cohorts) > 1:
                                                st.markdown(f"**📊 Combined Learning Progression: {selected_content_area}**")
                                                st.caption(f"Aggregated data from {len(selected_cohorts)} cohorts: {', '.join(str(c) for c in selected_cohorts)}")
                                            else:
                                                st.markdown(f"**📈 Learning Progression: {selected_content_area}**")
                                                st.caption(f"Data from {selected_cohorts[0]} cohort")
                                            
                                            # Create display version
                                            display_trajectory = trajectory_summary[['exam_round', 'Total_Students', 'Cohort_Pct', 'National_Pct', 'Gap_vs_National']].copy()
                                            display_trajectory = display_trajectory.rename(columns={
                                                'exam_round': 'Exam Period',
                                                'Total_Students': 'Students',
                                                'Cohort_Pct': 'Cohort %',
                                                'National_Pct': 'National %',
                                                'Gap_vs_National': 'Gap vs National'
                                            })
                                            
                                            # Format percentages
                                            display_trajectory['Cohort %'] = display_trajectory['Cohort %'].apply(lambda x: f"{x:.1f}%")
                                            display_trajectory['National %'] = display_trajectory['National %'].apply(lambda x: f"{x:.1f}%")
                                            display_trajectory['Gap vs National'] = display_trajectory['Gap vs National'].apply(lambda x: f"{x:+.1f}%")
                                            
                                            st.dataframe(display_trajectory, use_container_width=True)
                                            
                                            # Create line chart visualization
                                            if len(trajectory_summary) > 1:
                                                # Prepare data for chart
                                                chart_data = trajectory_summary[['exam_round', 'Cohort_Pct', 'National_Pct', 'exam_order']].copy()
                                                
                                                # Melt for line chart
                                                chart_data_long = chart_data.melt(
                                                    id_vars=['exam_round', 'exam_order'],
                                                    value_vars=['Cohort_Pct', 'National_Pct'],
                                                    var_name='Performance_Type',
                                                    value_name='Percentage'
                                                )
                                                
                                                # Create line chart
                                                line_chart = alt.Chart(chart_data_long).mark_line(point=True, strokeWidth=3).encode(
                                                    x=alt.X('exam_order:O', title='Exam Period', 
                                                           axis=alt.Axis(labelExpr="datum.value == 1 ? 'Spring MS1' : datum.value == 2 ? 'Fall MS2' : 'Spring MS2'")),
                                                    y=alt.Y('Percentage:Q', title='Percentage Correct', scale=alt.Scale(domain=[0, 100])),
                                                    color=alt.Color('Performance_Type:N', 
                                                                   scale=alt.Scale(domain=['Cohort_Pct', 'National_Pct'], 
                                                                                 range=['#1f77b4', '#ff7f0e']),
                                                                   legend=alt.Legend(title="Performance", 
                                                                                   labelExpr="datum.value == 'Cohort_Pct' ? 'Cohort Performance' : 'National Benchmark'")),
                                                    tooltip=['exam_round:N', 'Performance_Type:N', 'Percentage:Q']
                                                ).properties(
                                                    height=300,
                                                    title=f"Learning Trajectory: {selected_content_area}"
                                                )
                                                
                                                st.altair_chart(line_chart, use_container_width=True)
                                                
                                                # Analysis insights
                                                st.markdown("**📊 Trajectory Analysis:**")
                                                
                                                # Calculate improvement and gap metrics
                                                first_pct = trajectory_summary.iloc[0]['Cohort_Pct']
                                                last_pct = trajectory_summary.iloc[-1]['Cohort_Pct']
                                                improvement = last_pct - first_pct
                                                latest_gap = trajectory_summary.iloc[-1]['Gap_vs_National']
                                                
                                                col1, col2 = st.columns(2)
                                                
                                                with col1:
                                                    if improvement > 5:
                                                        st.success(f"📈 **Strong Learning Curve**: {improvement:+.1f}% improvement from MS1 to MS2")
                                                    elif improvement > 0:
                                                        st.info(f"📊 **Steady Progress**: {improvement:+.1f}% improvement over time")
                                                    else:
                                                        st.warning(f"📉 **Learning Decay**: {improvement:+.1f}% change - may need curriculum reinforcement")
                                                
                                                with col2:
                                                    # Gap analysis
                                                    if latest_gap >= 5:
                                                        st.success(f"🎯 **Above National**: Currently {latest_gap:+.1f}% vs national average")
                                                    elif latest_gap >= -5:
                                                        st.info(f"➖ **Near National**: Currently {latest_gap:+.1f}% vs national average")
                                                    else:
                                                        st.error(f"⚠️ **Below National**: Currently {latest_gap:+.1f}% vs national average")
                                            else:
                                                # Single exam period - can't show trends
                                                st.info("📊 **Single Exam Period**: Need multiple exam periods to show learning trajectory trends.")
                                                # Initialize variables for logging
                                                improvement = 0
                                                latest_gap = trajectory_summary.iloc[0]['Gap_vs_National'] if len(trajectory_summary) > 0 else 0
                                            
                                            # Log trajectory analysis
                                            log_feature_interaction(current_user, "content_trajectory_analysis", {
                                                "content_area": selected_content_area,
                                                "cohorts_analyzed": selected_cohorts,
                                                "exam_periods": len(trajectory_summary),
                                                "improvement": improvement,
                                                "latest_gap": latest_gap,
                                                "total_students": trajectory_summary['Total_Students'].sum(),
                                                "was_featured_selection": bool('featured_selection' in locals() and featured_selection),
                                                "multi_cohort": len(selected_cohorts) > 1
                                            })
                            
                                            # Enhanced "Coming Soon" based on what users will want
                                            st.markdown("---")
                                            st.markdown("💡 **What's Next? Click a feature:**")
                                            
                                            # Create columns for buttons
                                            if len(selected_cohorts) > 1:
                                                col1, col2 = st.columns(2)
                                                
                                                with col1:
                                                    if st.button("🔍 Individual Cohort Trajectories", 
                                                                use_container_width=True,
                                                                help="Compare 2022 vs 2023 vs 2024 learning curves separately"):
                                                        st.success("🚧 **Coming Soon!** Individual cohort trajectory comparison is in development.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "individual_cohort_trajectories",
                                                            "context": "multi_cohort_analysis",
                                                            "current_cohorts": selected_cohorts,
                                                            "content_area": selected_content_area
                                                        })
                                                    
                                                    if st.button("🧠 Competency-Level Trending", 
                                                                use_container_width=True,
                                                                help="Track Diagnosis vs Foundation vs Gen Principles over time"):
                                                        st.success("🚧 **Coming Soon!** Competency-level progression tracking is being built.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "competency_level_trending", 
                                                            "context": "multi_cohort_analysis",
                                                            "current_cohorts": selected_cohorts,
                                                            "content_area": selected_content_area
                                                        })
                                                
                                                with col2:
                                                    if st.button("📊 Multi-Content Area Dashboard", 
                                                                use_container_width=True,
                                                                help="See all content area trajectories at once"):
                                                        st.success("🚧 **Coming Soon!** Multi-content area dashboard is in development.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "multi_content_area_dashboard",
                                                            "context": "multi_cohort_analysis", 
                                                            "current_cohorts": selected_cohorts,
                                                            "content_area": selected_content_area
                                                        })
                                            else:
                                                col1, col2 = st.columns(2)
                                                
                                                with col1:
                                                    if st.button("📈 Multi-Cohort Comparison Charts", 
                                                                use_container_width=True,
                                                                help="Compare this cohort vs previous years"):
                                                        st.success("🚧 **Coming Soon!** Multi-cohort comparison charts are in development.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "multi_cohort_comparison_charts",
                                                            "context": "single_cohort_analysis",
                                                            "current_cohorts": selected_cohorts,
                                                            "content_area": selected_content_area
                                                        })
                                                    
                                                    if st.button("🧠 Competency-Level Trending", 
                                                                use_container_width=True,
                                                                help="Track Diagnosis vs Foundation vs Gen Principles over time"):
                                                        st.success("🚧 **Coming Soon!** Competency-level progression tracking is being built.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "competency_level_trending",
                                                            "context": "single_cohort_analysis", 
                                                            "current_cohorts": selected_cohorts,
                                                            "content_area": selected_content_area
                                                        })
                                                
                                                with col2:
                                                    if st.button("🎯 AI Content Area Recommendations", 
                                                                use_container_width=True,
                                                                help="AI-suggested areas to investigate based on your data"):
                                                        st.success("🚧 **Coming Soon!** AI-powered content recommendations are being developed.")
                                                        log_feature_interaction(current_user, "feature_request_click", {
                                                            "requested_feature": "ai_content_recommendations",
                                                            "context": "single_cohort_analysis",
                                                            "current_cohorts": selected_cohorts, 
                                                            "content_area": selected_content_area
                                                        })
                                            
                                        else:
                                            st.info("No data available for the selected content area and exam combination.")
                                    
                                else:
                                    st.warning("No valid trajectory data found after cleaning.")
                            else:
                                st.info("No trajectory data available for the selected cohorts and CBSE exams.")
                        else:
                            st.warning("⚠️ **No trajectory data available** for the selected cohorts and CBSE exams. This could mean:")
                            st.markdown("- No students in selected cohorts have taken CBSE exams with QLF data")
                            st.markdown("- Data synchronization issue between student records and QLF responses")
                    
                    except Exception as e:
                        st.error(f"Error processing trajectory data: {str(e)}")
                        st.info("📝 **Trajectory analysis unavailable** - this feature requires CBSE exam data with student enrollment information.")
            
    else:
        # Guide users to make selections
        st.markdown("## 🎯 Welcome to Cohort Analytics")
        st.markdown("**Get started by selecting filters in the sidebar:**")
       
        col1, col2 = st.columns(2)
       
        with col1:
            st.markdown("### 📚 **Step 1: Choose Cohorts**")
            if not selected_cohorts:
                st.info("👈 Select one or more cohorts from the sidebar to compare performance across graduation years.")
            else:
                st.success(f"✅ {len(selected_cohorts)} cohort(s) selected")
       
        with col2:
            st.markdown("### 📝 **Step 2: Choose Exams**")
            if not selected_exams:
                st.info("👈 Select one or more exams from the sidebar to analyze specific assessment periods.")
            else:
                st.success(f"✅ {len(selected_exams)} exam(s) selected")
       
        if selected_cohorts and not selected_exams:
            st.warning("⚠️ Please select at least one exam to begin analysis.")
        elif not selected_cohorts and selected_exams:
            st.warning("⚠️ Please select at least one cohort to begin analysis.")
       
        # Show available options to help users
        st.markdown("---")
        st.markdown("### 📊 **Available Data:**")
       
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Cohorts Available:**")
            for cohort in available_cohorts:
                st.markdown(f"- {cohort}")
       
        with col2:
            st.markdown("**Exams Available:**")
            for exam in available_exams:
                st.markdown(f"- {exam}")

# --- COMMUNICATION SKILLS ANALYTICS (CLA) ---
elif page == "🗣️ CLA Analytics":
    st.markdown("# 🗣️ Communication Skills Analytics")
    st.markdown("*Communications Learning Assessment (CLA) Performance Dashboard*")

    # Log CLA page access
    log_cla_action(current_user, "cla_page_access", {
        "access_timestamp": datetime.datetime.now().isoformat()
    })
    
    # Try to load CLA data
    cla_data = load_cla_data()
    
    if cla_data.empty:
        st.warning("⚠️ CLA data not found. Please ensure 'cla_results.csv' is in the project directory.")
        st.info("🚧 **CLA Dashboard Coming Soon!** This section will provide communication skills analytics.")
    else:
        st.success("✅ CLA data loaded successfully!")
        
        # Show basic data info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("👥 Students", cla_data['student_id'].nunique())
        with col2:
            st.metric("📚 Vignettes Assigned", cla_data['exercise'].nunique())
        with col3:
            st.metric("📋 Total Assessments", len(cla_data))
        
        # Patient Vignette Completion Tracking
        with st.container():
            st.markdown("### 🏥 Patient Vignette Completion Tracking")
            st.markdown("---")
        
        # Calculate completion by exercise/patient
        total_students = cla_data['student_id'].nunique()
        completed_data = cla_data[cla_data['completed'] == True]
        
        exercise_completions = completed_data.groupby(['exercise', 'Patient_Name'])['student_id'].nunique().reset_index()
        exercise_completions.columns = ['exercise', 'patient_name', 'students_completed']
        exercise_completions['completion_rate'] = (exercise_completions['students_completed'] / total_students * 100).round(1)
        exercise_completions = exercise_completions.sort_values('exercise')
        
        # Display in 4 columns (2 rows of 4)
        for row in range(2):
            cols = st.columns(4)
            for col_idx in range(4):
                exercise_idx = row * 4 + col_idx
                if exercise_idx < len(exercise_completions):
                    exercise_data = exercise_completions.iloc[exercise_idx]
                    exercise_num = int(exercise_data['exercise'])
                    patient = exercise_data['patient_name']
                    completed = int(exercise_data['students_completed'])
                    rate = exercise_data['completion_rate']
                    
                    with cols[col_idx]:
                        st.metric(
                            f"Vignette {exercise_num}: {patient}",
                            f"{completed}/{total_students}",
                            delta=f"{rate}%",
                            help=f"Students who completed the {patient} patient vignette"
                        )

            st.markdown("")
        
        # Patient Centered Behaviors - Skills Performance  
        with st.container():
            st.markdown("### 🗣️ Patient Centered Behaviors: Skills")
            st.markdown("---")
        
        # Calculate performance by skill
        valid_data = cla_data[(cla_data['PCB_Skill'] != 'NA') & (cla_data['correct'].notna())]
        
        if not valid_data.empty:
            skills_performance = valid_data.groupby('PCB_Skill').agg({
                'correct': ['count', 'sum']
            })
            skills_performance.columns = ['total', 'correct']
            skills_performance['percentage'] = (skills_performance['correct'] / skills_performance['total'] * 100).round(1)
            
            # Display in columns
            skill_cols = st.columns(4)
            skill_names = ['Relevancy', 'Responding', 'Understandability', 'Exploring']
            
            for i, skill in enumerate(skill_names):
                if skill in skills_performance.index:
                    pct = skills_performance.loc[skill, 'percentage']
                    total = skills_performance.loc[skill, 'total']
                    
                    with skill_cols[i]:
                        st.metric(
                            f"🗣️ {skill}", 
                            f"{pct}%",
                            delta=f"{total} assessments",
                            help=f"Percentage of correct responses for {skill} communication skill"
                        )

            st.markdown("")
        
        # Learning Objectives Performance
        with st.container():
            st.markdown("### 🎯 Patient Centered Behaviors: Learning Objectives")
            st.markdown("---")
        
        # Calculate performance by learning objective
        valid_objective_data = cla_data[(cla_data['PCB_Learning_Objective'] != 'NA') & (cla_data['correct'].notna())]
        
        if not valid_objective_data.empty:
            objectives_performance = valid_objective_data.groupby('PCB_Learning_Objective').agg({
                'correct': ['count', 'sum']
            })
            objectives_performance.columns = ['total', 'correct']
            objectives_performance['percentage'] = (objectives_performance['correct'] / objectives_performance['total'] * 100).round(1)
            
            # Display in columns
            obj_cols = st.columns(2)
            objective_names = ['Providing Information', 'Responding to Emotion']
            
            for i, objective in enumerate(objective_names):
                if objective in objectives_performance.index:
                    pct = objectives_performance.loc[objective, 'percentage']
                    total = objectives_performance.loc[objective, 'total']
                    
                    with obj_cols[i]:
                        st.metric(
                            f"📋 {objective}", 
                            f"{pct}%",
                            delta=f"{total} assessments",
                            help=f"Percentage of correct responses for {objective} learning objective"
                        )

            st.markdown("")
        
        
        # Individual PCB Labels Performance (Ranked)
        with st.container():
            st.markdown("### 📊 Individual Patient Centered Behaviors")
            st.markdown("---")
        
        # Calculate performance by PCB_Label
        valid_label_data = cla_data[(cla_data['PCB_Label'] != 'NA') & (cla_data['correct'].notna())]
        
        if not valid_label_data.empty:
            labels_performance = valid_label_data.groupby('PCB_Label').agg({
                'correct': ['count', 'sum']
            })
            labels_performance.columns = ['total', 'correct']
            labels_performance['percentage'] = (labels_performance['correct'] / labels_performance['total'] * 100).round(1)
            
            # Sort by percentage (highest first)
            labels_performance = labels_performance.sort_values('percentage', ascending=False).reset_index()
            
            # Create bar chart using Altair
            chart = alt.Chart(labels_performance).mark_bar().encode(
                x=alt.X('PCB_Label:N', 
                       sort=alt.SortField(field='percentage', order='descending'),
                       title='Patient Centered Behaviors',
                       axis=alt.Axis(labelAngle=-45, labelLimit=150)),
                y=alt.Y('percentage:Q', 
                       title='Percentage Correct',
                       scale=alt.Scale(domain=[0, 100])),
                tooltip=['PCB_Label:N', 'percentage:Q', 'total:Q'],
                color=alt.value('#1f77b4')
            ).properties(
                width=800,
                height=400,
                title="Individual PCB Performance (Ranked Highest to Lowest)"
            )
            
            st.altair_chart(chart, use_container_width=True)

            # Log chart interaction
            log_cla_action(current_user, "pcb_labels_chart_viewed", {
                "chart_type": "individual_pcb_performance",
                "total_labels": len(labels_performance),
                "highest_performing": labels_performance.iloc[0]['PCB_Label'][:50],
                "lowest_performing": labels_performance.iloc[-1]['PCB_Label'][:50]
            })
            
            # Show top and bottom performers
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🏆 Top 3 Performing Behaviors:**")
                for i in range(min(3, len(labels_performance))):
                    row = labels_performance.iloc[i]
                    st.markdown(f"{i+1}. {row['PCB_Label'][:50]}... ({row['percentage']:.1f}%)")
            
            with col2:
                st.markdown("**📈 Bottom 3 - Need Focus:**")
                for i in range(min(3, len(labels_performance))):
                    row = labels_performance.iloc[-(i+1)]
                    st.markdown(f"{len(labels_performance)-i}. {row['PCB_Label'][:50]}... ({row['percentage']:.1f}%)")

            st.markdown("")
        
        
        # Coming Soon Feature Button with Analytics Tracking
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if st.button("🔍 Access Individual Student CLA Analysis", 
                        use_container_width=True,
                        help="Click to express interest in individual student communication analysis features"):
                
                # Log feature interest for analytics
                log_cla_action(current_user, "feature_interest_click", {
                    "requested_feature": "individual_student_cla_analysis",
                    "feature_category": "student_lookup",
                    "click_timestamp": datetime.datetime.now().isoformat(),
                    "user_interest": "individual_cla_analysis"
                })
                
                # Show coming soon message
                st.success("🚧 **Coming Soon!** Individual student CLA analysis is in development.")
                st.info("📊 **Thanks for your interest!** Your feedback helps us prioritize new features.")
                
                # Show what's planned
                st.markdown("**🔮 Planned Features:**")
                st.markdown("- Individual student communication skills dashboard")
                st.markdown("- Exercise-by-exercise completion tracking")
                st.markdown("- Patient scenario performance analysis")
                st.markdown("- Communication skills improvement recommendations")

# --- ANALYTICS DASHBOARD (Admin Only) ---
elif page == "📊 Analytics" and is_admin(current_user):
    st.markdown("# 📊 Research Analytics Dashboard")
    st.markdown("*User engagement and feature usage analytics*")
   
    analytics_file = "experiment_analytics.json"
   
    if not os.path.exists(analytics_file):
        st.info("📊 No analytics data available yet. Data will appear as users interact with the dashboard.")
        st.stop()
   
    # Load analytics data
    analytics_data = []
    try:
        with open(analytics_file, "r") as f:
            for line in f:
                analytics_data.append(json.loads(line.strip()))
    except Exception as e:
        st.error(f"Error loading analytics: {e}")
        st.stop()
   
    if not analytics_data:
        st.info("📊 No analytics data available yet.")
        st.stop()
   
    # Convert to DataFrame
    df = pd.DataFrame(analytics_data)
    df['datetime'] = pd.to_datetime(df['datetime'])
   
    # Overview metrics
    st.subheader("📈 Overview Metrics")
    col1, col2, col3, col4 = st.columns(4)
   
    with col1:
        unique_users = df['user_email'].nunique()
        st.metric("👥 Total Users", unique_users)
   
    with col2:
        total_actions = len(df)
        st.metric("📊 Total Actions", total_actions)
   
    with col3:
        unique_sessions = df['session_id'].nunique()
        st.metric("🔄 Total Sessions", unique_sessions)
   
    with col4:
        active_today = df[df['datetime'].dt.date == pd.Timestamp.now().date()]['user_email'].nunique()
        st.metric("📅 Active Today", active_today)
   
    # User engagement analysis
    st.subheader("👥 User Engagement")
   
    user_activity = df.groupby('user_email').agg({
        'action': 'count',
        'session_id': 'nunique',
        'datetime': ['min', 'max']
    }).round(2)
   
    user_activity.columns = ['Total Actions', 'Sessions', 'First Activity', 'Last Activity']
    user_activity = user_activity.sort_values('Total Actions', ascending=False)
   
    st.dataframe(user_activity, use_container_width=True)
   
    # Feature usage analysis
    st.subheader("🎯 Feature Usage")
   
    page_views = df[df['action'] == 'page_view']['details'].apply(lambda x: x.get('mode', 'Unknown') if isinstance(x, dict) else 'Unknown').value_counts()
   
    col1, col2 = st.columns(2)
   
    with col1:
        st.markdown("**Page Views**")
        st.dataframe(page_views.to_frame('Count'))
   
    with col2:
        # Feature interactions
        feature_interactions = df[df['action'] == 'feature_interaction']['details'].apply(lambda x: x.get('feature', 'Unknown') if isinstance(x, dict) else 'Unknown').value_counts()
        st.markdown("**Feature Interactions**")
        if not feature_interactions.empty:
            st.dataframe(feature_interactions.to_frame('Count'))
        else:
            st.info("No feature interactions recorded yet.")
   
    # PDF Report Analytics Section
    pdf_reports = df[df['action'] == 'feature_interaction']
    pdf_reports = pdf_reports[pdf_reports['details'].apply(lambda x: x.get('feature') == 'pdf_report_generation' if isinstance(x, dict) else False)]
   
    # INSIGHTS access tracking
    insights_clicks = df[df['action'] == 'feature_interaction']
    insights_clicks = insights_clicks[insights_clicks['details'].apply(lambda x: x.get('feature') == 'insights_access_attempt' if isinstance(x, dict) else False)]
   
    if not pdf_reports.empty or not insights_clicks.empty:
        st.subheader("📄 PDF Report & Feature Interest Analytics")
       
        # Combined metrics row
        col1, col2, col3, col4 = st.columns(4)
       
        with col1:
            total_pdfs = len(pdf_reports)
            st.metric("📊 PDFs Generated", total_pdfs)
       
        with col2:
            total_insights_clicks = len(insights_clicks)
            st.metric("🔍 INSIGHTS® Clicks", total_insights_clicks)
       
        with col3:
            if not pdf_reports.empty:
                unique_advisors = pdf_reports['user_email'].nunique()
                st.metric("👥 Active Advisors", unique_advisors)
            else:
                st.metric("👥 Active Advisors", 0)
       
        with col4:
            if total_pdfs > 0 and total_insights_clicks > 0:
                insights_interest_rate = (total_insights_clicks / (total_pdfs + total_insights_clicks)) * 100
                st.metric("📈 INSIGHTS® Interest", f"{insights_interest_rate:.1f}%")
            else:
                st.metric("📈 INSIGHTS® Interest", "N/A")
   
    if not pdf_reports.empty:
        # Extract PDF report details
        pdf_details = []
        for _, row in pdf_reports.iterrows():
            details = row['details'].get('details', {})
            pdf_details.append({
                'user': row['user_email'],
                'timestamp': row['datetime'],
                'student_id': details.get('student_id', 'Unknown'),
                'student_name': details.get('student_name', 'Unknown'),
                'num_exams': details.get('num_exams', 0),
                'has_epc': details.get('has_epc_data', False),
                'has_qlf': details.get('has_qlf_data', False)
            })
       
        pdf_df = pd.DataFrame(pdf_details)
       
        # Most active advisors
        st.markdown("**Most Active Advisors (PDF Generation)**")
        advisor_activity = pdf_df.groupby('user').agg({
            'student_id': 'count',
            'timestamp': ['min', 'max']
        }).round(2)
        advisor_activity.columns = ['Reports Generated', 'First Report', 'Latest Report']
        advisor_activity = advisor_activity.sort_values('Reports Generated', ascending=False)
        st.dataframe(advisor_activity, use_container_width=True)
       
        # Students most reported on
        st.markdown("**Students Most Frequently Reported On**")
        student_reports = pdf_df.groupby(['student_name', 'student_id']).agg({
            'user': 'count',
            'timestamp': 'max'
        }).rename(columns={'user': 'Report Count', 'timestamp': 'Latest Report'})
        student_reports = student_reports.sort_values('Report Count', ascending=False).head(10)
        st.dataframe(student_reports, use_container_width=True)
       
        # Data quality metrics
        st.markdown("**Report Data Quality**")
        quality_col1, quality_col2, quality_col3 = st.columns(3)
       
        with quality_col1:
            with_epc = pdf_df['has_epc'].sum()
            st.metric("Reports with EPC Data", f"{with_epc}/{len(pdf_df)}")
       
        with quality_col2:
            with_qlf = pdf_df['has_qlf'].sum()
            st.metric("Reports with QLF Data", f"{with_qlf}/{len(pdf_df)}")
       
        with quality_col3:
            complete_reports = pdf_df[(pdf_df['has_epc']) & (pdf_df['has_qlf'])].shape[0]
            st.metric("Complete Reports", f"{complete_reports}/{len(pdf_df)}")
       
        # Usage over time
        if len(pdf_df) > 1:
            st.markdown("**PDF Generation Over Time**")
            pdf_df['date'] = pd.to_datetime(pdf_df['timestamp']).dt.date
            daily_reports = pdf_df.groupby('date').size().reset_index(name='reports')
           
            time_chart = alt.Chart(daily_reports).mark_bar().encode(
                x=alt.X('date:T', title='Date'),
                y=alt.Y('reports:Q', title='Reports Generated'),
                tooltip=['date:T', 'reports:Q']
            ).properties(height=300, title="Daily PDF Report Generation")
            st.altair_chart(time_chart, use_container_width=True)
   
    # INSIGHTS Interest Analytics
    if not insights_clicks.empty:
        st.markdown("**🔍 INSIGHTS® Feature Interest**")
       
        # Extract insights click details
        insights_details = []
        for _, row in insights_clicks.iterrows():
            details = row['details'].get('details', {})
            insights_details.append({
                'user': row['user_email'],
                'timestamp': row['datetime'],
                'student_id': details.get('student_id', 'Unknown'),
                'student_name': details.get('student_name', 'Unknown'),
                'student_first_name': details.get('student_first_name', 'Unknown'),
                'cohort_year': details.get('cohort_year', 'Unknown')
            })
       
        insights_df = pd.DataFrame(insights_details)
       
        col1, col2 = st.columns(2)
       
        with col1:
            st.markdown("**Users Most Interested in INSIGHTS®**")
            user_interest = insights_df.groupby('user').agg({
                'student_id': 'count',
                'timestamp': 'max'
            }).rename(columns={'student_id': 'Clicks', 'timestamp': 'Latest Click'})
            user_interest = user_interest.sort_values('Clicks', ascending=False)
            st.dataframe(user_interest, use_container_width=True)
       
        with col2:
            st.markdown("**Students Users Want INSIGHTS® For**")
            student_interest = insights_df.groupby(['student_name', 'cohort_year']).agg({
                'user': 'count',
                'timestamp': 'max'
            }).rename(columns={'user': 'Interest Count', 'timestamp': 'Latest Interest'})
            student_interest = student_interest.sort_values('Interest Count', ascending=False).head(10)
            st.dataframe(student_interest, use_container_width=True)
       
        st.success(f"🎯 **Feature Validation**: {len(insights_clicks)} clicks show strong interest in student-facing INSIGHTS® portal!")
   
    if pdf_reports.empty and insights_clicks.empty:
        st.subheader("📄 PDF Report & Feature Interest Analytics")
        st.info("No PDF reports or feature interactions yet. This section will show detailed usage analytics once advisors start using the features.")
        st.markdown("**What you'll see here:**")
        st.markdown("- PDF report generation analytics")
        st.markdown("- INSIGHTS® feature interest tracking")
        st.markdown("- User engagement patterns")
        st.markdown("- Feature validation metrics")
   
    # Session analysis
    st.subheader("⏱️ Session Analysis")
   
    session_data = df[df['action'] == 'session_activity'].copy()
    if not session_data.empty:
        session_durations = session_data['details'].apply(lambda x: x.get('session_duration_minutes', 0) if isinstance(x, dict) else 0)
       
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_session = session_durations.mean()
            st.metric("⏱️ Avg Session (min)", f"{avg_session:.1f}")
        with col2:
            max_session = session_durations.max()
            st.metric("🏆 Longest Session (min)", f"{max_session:.1f}")
        with col3:
            total_time = session_durations.sum()
            st.metric("⏰ Total Time (hours)", f"{total_time/60:.1f}")
       
        # Session duration distribution
        st.markdown("**Session Duration Distribution**")
        duration_chart = alt.Chart(pd.DataFrame({'duration': session_durations})).mark_bar().encode(
            x=alt.X('duration:Q', bin=True, title='Session Duration (minutes)'),
            y=alt.Y('count()', title='Number of Sessions')
        ).properties(height=300)
        st.altair_chart(duration_chart, use_container_width=True)
    else:
        st.info("No session duration data available yet.")
   
    # Most recent activity
    st.subheader("🕐 Recent Activity")
    recent_activity = df.sort_values('datetime', ascending=False).head(20)[['datetime', 'user_email', 'action', 'page_mode']].copy()
    recent_activity['datetime'] = recent_activity['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    st.dataframe(recent_activity, use_container_width=True)
   
    # Raw data export for researchers
    st.subheader("📤 Data Export")
    col1, col2 = st.columns(2)
   
    with col1:
        if st.button("📁 Export All Analytics Data"):
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="Download Complete Analytics CSV",
                data=csv_data,
                file_name=f"dashboard_analytics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
   
    with col2:
        # PDF-specific export
        pdf_reports = df[df['action'] == 'feature_interaction']
        pdf_reports = pdf_reports[pdf_reports['details'].apply(lambda x: x.get('feature') == 'pdf_report_generation' if isinstance(x, dict) else False)]
       
        # INSIGHTS clicks export
        insights_clicks = df[df['action'] == 'feature_interaction']
        insights_clicks = insights_clicks[insights_clicks['details'].apply(lambda x: x.get('feature') == 'insights_access_attempt' if isinstance(x, dict) else False)]
       
        if not pdf_reports.empty:
            if st.button("📄 Export PDF Analytics"):
                pdf_csv = pdf_reports.to_csv(index=False)
                st.download_button(
                    label="Download PDF Analytics CSV",
                    data=pdf_csv,
                    file_name=f"pdf_analytics_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
       
        if not insights_clicks.empty:
            if st.button("🔍 Export INSIGHTS® Interest Data"):
                insights_csv = insights_clicks.to_csv(index=False)
                st.download_button(
                    label="Download INSIGHTS® Analytics CSV",
                    data=insights_csv,
                    file_name=f"insights_interest_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
       
        if pdf_reports.empty and insights_clicks.empty:
            st.info("No feature-specific analytics to export yet")

else:
    st.error("Access denied. Page not found or insufficient permissions.")