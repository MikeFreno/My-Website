from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date, datetime
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PP_UPLOAD_FOLDER = 'static/uploads/profile_pictures'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = "#@4DFsdf;[34AsD1SKb"
app.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000
app.config['PP_FOLDER'] = PP_UPLOAD_FOLDER

ckeditor = CKEditor(app)
Bootstrap(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL","sqlite:///site.db").replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
gravatar = Gravatar(app, size=100, rating='g', default='identicon', force_default=False, force_lower=False,
                    use_ssl=False,
                    base_url=None)

login_manager = LoginManager()
login_manager.init_app(app)


class BlogPost(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), unique=False, nullable=False)
    subtitle = db.Column(db.String(256), nullable=False)
    date = db.Column(db.String(256), nullable=False)
    doy = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    cover_photo = db.Column(db.String, unique=False, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")


class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), unique=False, nullable=False)
    subtitle = db.Column(db.String(256), nullable=True)
    body = db.Column(db.Text, nullable=False)
    cover_photo = db.Column(db.String, unique=False, nullable=True)
    date = db.Column(db.String(256), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="projects")
    comments = relationship("Comment", back_populates="parent_project")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    parent_project = relationship("Project", back_populates="comments")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True)
    password = db.Column(db.String(512))
    name = db.Column(db.String(128))
    profile_picture = db.Column(db.String(256), nullable=True)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author", lazy='dynamic', )
    projects = relationship("Project", back_populates="author")


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    message = StringField("Message")
    submit = SubmitField("Send Message")


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField("Confirm Password", validators=[DataRequired(), Length(min=8)])
    sign_up = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    sign_in = SubmitField('Sign In')


class NewPostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    cover_photo = StringField("Blog Image URL")
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class NewProjectForm(FlaskForm):
    title = StringField("Project Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    cover_photo = StringField("Project Cover Photo URL")
    body = CKEditorField("Project Text Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class CommentForm(FlaskForm):
    body = CKEditorField("Comment", validators=[DataRequired()])
    submit = SubmitField("Post")


class ChangePasswordForm(FlaskForm):
    confirm_old_password = PasswordField("Confirm Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_new_password = PasswordField("Confirm New Password", validators=[DataRequired()])
    submit = SubmitField("Change Password")


class PPForm(FlaskForm):
    submit = SubmitField("Upload")


class DeleteProfileForm(FlaskForm):
    password = PasswordField("Enter Password", validators=[DataRequired()])
    submit = SubmitField("Delete Account")


with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/', methods=['GET', 'POST'])
def home():
    form = ContactForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash("Email Sent")
            send_contact_email(name=request.form['name'], email=request.form['email'], message=request.form['message'])
    return render_template("index.html", year=date.today().year, logged_in=current_user.is_authenticated, form=form, user=current_user)


@app.route('/blog')
def blog():
    posts = BlogPost.query.all()
    return render_template("blog.html", logged_in=current_user.is_authenticated, all_posts=posts,
                           doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash("Email Sent")
            send_contact_email(name=request.form['name'], email=request.form['email'], message=request.form['message'])
    return render_template("contact_me.html", year=date.today().year, logged_in=current_user.is_authenticated, form=form, user=current_user)

@app.route('/projects')
def projects():
    projects_ = Project.query.all()
    return render_template("projects.html", logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, all_projects=projects_)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data == form.password_confirm.data:
            nameFix = request.form['name'].replace(' ', '_')
            try:
                new_user = User(
                    email=form.email.data,
                    password=generate_password_hash(form.password.data, method='pbkdf2:sha256',
                                                    salt_length=8),
                    name=nameFix
                )
                db.session.add(new_user)
                db.session.commit()
                user_check = User.query.filter_by(email=form.email.data).first()
                login_user(user_check)
                return redirect(url_for("settings"))
            except IntegrityError:
                flash('Email already registered!')
                return redirect(url_for('register'))
        else:
            flash('Passwords do not match!')
            return redirect(url_for('register'))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    logout_user()
    form = LoginForm()
    if form.validate_on_submit():
        user_check = User.query.filter_by(email=form.email.data).first()
        if user_check:
            if check_password_hash(user_check.password, form.password.data):
                login_user(user_check)
                return redirect(url_for('settings'))
            else:
                flash('Email or password is invalid.')
                return redirect(url_for('login'))
        else:
            flash('Email or password is invalid.')
            return redirect(url_for('login'))
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    picture_form = PPForm()
    password_form = ChangePasswordForm()
    delete_form = DeleteProfileForm()
    if request.method == 'POST':
        if 'file' not in request.files:
            pass
        else:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['PP_FOLDER'], filename))
                path = f'static/uploads/profile_pictures/{filename}'
                current_user.profile_picture = path
                db.session.commit()
            else:
                flash("Invalid File")
    if password_form.validate_on_submit():
        if check_password_hash(current_user.password, password_form.confirm_old_password.data):
            if password_form.confirm_new_password.data == password_form.new_password.data:
                current_user.password = generate_password_hash(password_form.confirm_new_password.data,
                                                               method='pbkdf2:sha256')
                db.session.commit()
                flash('Password Changed.')
                return redirect(url_for('settings', _anchor='form2'))
            else:
                flash("New Password Fields Must Match")
        else:
            flash("Incorrect Current Password")
    if delete_form.validate_on_submit():
        if check_password_hash(current_user.password, delete_form.password.data):
            db.session.delete(current_user)
            db.session.commit()
            flash('Account Deleted')
            return redirect(url_for('home'))
    return render_template('settings.html', logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, picture_form=picture_form, password_form=password_form,
                           delete_form=delete_form)



@app.route("/new-post", methods=['GET', 'POST'])
@admin_only
def add_new_blog():
    form = NewPostForm()
    if form.validate_on_submit():
        if 'file' not in request.files:
            pass
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        if form.cover_photo.data == '':
            option_result = f'static/uploads/{filename}'
        else:
            option_result = form.cover_photo.data
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            cover_photo=option_result,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
            doy=datetime.now().timetuple().tm_yday
        )
        db.session.add(new_post)
        db.session.commit()
        new = BlogPost.query.filter(BlogPost.title == new_post.title, BlogPost.subtitle == new_post.subtitle).first()
        return redirect(url_for('show_post', post_id=new.id))
    return render_template('new_blog_post.html', form=form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user)


@app.route("/edit_post/<int:post_id>", methods=['GET', 'POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = NewPostForm(
        title=post.title,
        subtitle=post.subtitle,
        body=post.body,
        cover_photo=post.cover_photo,
        author=current_user,
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.cover_photo.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('new_blog_post.html', form=edit_form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                body=form.body.data,
                author=current_user,
                parent_post=requested_post
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id, _anchor="past_last"))
        else:
            flash('Must be logged in to comment')
            return redirect(url_for('login'))
    return render_template("post.html", post=requested_post, user=current_user, logged_in=current_user.is_authenticated,
                           form=form)


@app.route("/new-project", methods=['GET', 'POST'])
@admin_only
def add_new_project():
    form = NewProjectForm()
    if form.validate_on_submit():
        if 'file' not in request.files:
            pass
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        if form.cover_photo.data == '':
            option_result = f'static/uploads/{filename}'
        else:
            option_result = form.cover_photo.data
        new_proj = Project(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            cover_photo=option_result,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_proj)
        db.session.commit()
        new = Project.query.filter(Project.title == new_proj.title, Project.subtitle == new_proj.subtitle).first()
        return redirect(url_for('show_project', proj_id=new.id))
    return render_template('new_project.html', form=form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user)


@app.route("/edit_project/<int:proj_id>", methods=['GET', 'POST'])
@admin_only
def edit_project(proj_id):
    project = Project.query.get(proj_id)
    edit_form = NewProjectForm(
        title=project.title,
        subtitle=project.subtitle,
        body=project.body,
        cover_photo=project.cover_photo,
        author=current_user,
    )
    if edit_form.validate_on_submit():
        project.title = edit_form.title.data
        project.subtitle = edit_form.subtitle.data
        project.cover_photo = edit_form.cover_photo.data
        project.author = current_user
        project.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_project", proj_id=project.id))
    return render_template('new_project.html', form=edit_form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user)


@app.route("/project/<int:proj_id>", methods=['GET', 'POST'])
def show_project(proj_id):
    form = CommentForm()
    requested_proj = Project.query.get(proj_id)
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                body=form.body.data,
                author=current_user,
                parent_project=requested_proj
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_project', proj_id=proj_id, _anchor="past_last"))
        else:
            flash('Must be logged in to comment')
            return redirect(url_for('login'))

    return render_template("project.html", proj=requested_proj, user=current_user,
                           logged_in=current_user.is_authenticated, form=form)


@app.route("/_deletepo/<int:post_id>", methods=['GET', 'POST', 'DELETE'])
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('blog', logged_in=current_user.is_authenticated,
                            doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user))


@app.route("/_deletepj/<int:proj_id>", methods=['GET', 'POST', 'DELETE'])
@admin_only
def delete_project(proj_id):
    proj_to_delete = Project.query.get(proj_id)
    db.session.delete(proj_to_delete)
    db.session.commit()
    return redirect(url_for('projects', logged_in=current_user.is_authenticated,
                            doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user))


@app.route("/_deletepj/<int:proj_id>/<int:comment_id>", methods=['GET', 'POST', 'DELETE'])
@login_required
def delete_project_comment(proj_id, comment_id):
    proj_to_delete_from = Project.query.get(proj_id).comments
    for comment in proj_to_delete_from:
        if comment.id == comment_id:
            db.session.delete(comment)
            db.session.commit()
    return redirect(url_for('show_project', proj_id=proj_id, _anchor='past_last'))


@app.route("/_deletepo/<int:post_id>/<int:comment_id>", methods=['GET', 'POST', 'DELETE'])
@login_required
def delete_post_comment(post_id, comment_id):
    post_to_delete_from = BlogPost.query.get(post_id).comments
    for comment in post_to_delete_from:
        if comment.id == comment_id:
            db.session.delete(comment)
            db.session.commit()
    return redirect(url_for('show_post', post_id=post_id, _anchor='past_last'))


def send_contact_email(name, email, message):
    email_body = f"Name: {name}\nEmail: {email}\nMessage: {message}"
    HOST = "michaelt.freno@proton.me"
    RECEIVER = 'michaelt.freno@gmail.com'
    msg = MIMEMultipart()
    msg['To'] = RECEIVER
    msg['From'] = HOST
    msg['Subject'] = "WEBSITE CONTACT"
    msg_ready = MIMEText(_text=email_body, _charset='utf-8')
    msg.attach(msg_ready)

    with smtplib.SMTP('127.0.0.1', 1025) as mail:
        mail.login(HOST, "broken")
        mail.sendmail(HOST, RECEIVER, msg.as_string())

    return redirect(url_for('home', _anchor="contact"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
