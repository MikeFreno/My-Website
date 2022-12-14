import os
from datetime import date, datetime
from functools import wraps
from dotenv import load_dotenv, find_dotenv

from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from libgravatar import Gravatar as G
from markupsafe import Markup
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import StringField, SubmitField, PasswordField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

from image_var import image

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PP_UPLOAD_FOLDER = 'static/uploads/profile_pictures'


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000
app.config['PP_FOLDER'] = PP_UPLOAD_FOLDER

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='identicon',
                    force_default=False,
                    use_ssl=False,
                    base_url=None)

ckeditor = CKEditor(app)
Bootstrap(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///site.db").replace("postgres://",
                                                                                                    "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    parent_comment = db.Column(db.Integer, nullable=True)
    parent_chain = db.Column(db.String(256), nullable=True)
    likes = db.Column(db.Integer, nullable=False)
    author = relationship("User", back_populates="comments")
    parent_post = relationship("BlogPost", back_populates="comments")
    parent_project = relationship("Project", back_populates="comments")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(128), unique=True)
    password = db.Column(db.String(512))
    name = db.Column(db.String(128))
    profile_picture = db.Column(db.String(256), nullable=True)
    liked_comments = db.Column(db.String(256))
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

class CommentReplyForm(FlaskForm):
    body = StringField("Comment", validators=[DataRequired()])
    parent_comment = HiddenField()
    parent_level = HiddenField()
    reply_submit = SubmitField("Post Reply")


class CommentForm(FlaskForm):
    body = StringField("Comment", validators=[DataRequired()])
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
    return render_template("index.html", year=date.today().year, logged_in=current_user.is_authenticated, form=form,
                           user=current_user)


@app.route('/blog')
def blog():
    posts = BlogPost.query.all()
    return render_template("blog.html", logged_in=current_user.is_authenticated, all_posts=posts,
                           doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user,
                           page="Blog")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            flash("Email Sent")
            send_contact_email(name=request.form['name'], email=request.form['email'], message=request.form['message'])
    return render_template("contact_me.html", year=date.today().year, logged_in=current_user.is_authenticated,
                           form=form, user=current_user, page="Contact")


@app.route('/projects')
def projects():
    projects_ = Project.query.all()
    return render_template("projects.html", logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, all_projects=projects_, page="Projects")


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
                    name=nameFix,
                    liked_comments='',
                )
                db.session.add(new_user)
                db.session.commit()
                user_check = User.query.filter_by(email=form.email.data).first()
                login_user(user_check)
                send_registration_email(name=request.form['name'], email=form.email.data)
                return redirect(url_for("settings"))
            except IntegrityError:
                flash('Email already registered!')
                return redirect(url_for('register'))
        else:
            flash('Passwords do not match!')
            return redirect(url_for('register'))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, page="Register")


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
                           user=current_user, page="Login")


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
                flash('Password Change Successful.')
                return redirect(url_for('settings', _anchor='form2'))
            else:
                flash("New Password Fields Must Match")
        else:
            flash("Incorrect Current Password")
    if delete_form.validate_on_submit():
        if check_password_hash(current_user.password, delete_form.password.data):
            db.session.delete(current_user)
            db.session.commit()
            return redirect(url_for('home'))
        else:
            flash("Incorrect Password")
    return render_template('settings.html', logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, picture_form=picture_form, password_form=password_form,
                           delete_form=delete_form, page="Settings")

@app.route("/user_page/<int:user_id>")
def user_page(user_id):
    shown_user = User.query.get(user_id)
    comments = shown_user.comments
    return render_template('user_page.html', shown_user=shown_user, logged_in=current_user.is_authenticated, year=date.today().year,
                           user=current_user, page="User Page", comment_list_length=comments.count())

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
                           year=date.today().year, user=current_user, page="New Blog")


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
        if 'file' not in request.files:
            pass
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        if edit_form.cover_photo.data == '':
            option_result = f'static/uploads/{filename}'
        else:
            option_result = edit_form.cover_photo.data

        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.cover_photo = option_result
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('new_blog_post.html', form=edit_form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user, page="Edit Blog")


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    replyform = CommentReplyForm()
    requested_post = BlogPost.query.get(post_id)
    comment_structure = order_comments(post_id)
    construct = ''
    for n in range(0, len(comment_structure)):
        parent_node = HTML_comment_constructor(comment_structure[n]['comment'])
        parent_HTML = Markup(f'''</ul><ul class="commentList"><li style="margin-left:10vw;margin-right:10vw;list-style:none;"><hr><div>{parent_node}</div></li>''')
        rest_of_node = reducer(comment_structure[n],'',1)
        full_node = parent_HTML+rest_of_node
        construct+=full_node
    if request.method == 'POST':
        if request.form.get('submit')=='Post':
            new_comment = Comment(
                body=request.form['comment'],
                author=current_user,
                parent_post=requested_post,
                likes=0,
                parent_comment=None,
                parent_chain="",
            )
            db.session.add(new_comment)
            new = Comment.query.filter(Comment.body == new_comment.body).order_by(Comment.id.desc()).first()
            like_comment_on_post(new)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id, _anchor=f'comment_marker_{new_comment.id}'))
        elif request.form.get('reply_submit')=='Post Reply':
            new_reply = Comment(
                body=request.form['comment_reply'],
                author=current_user,
                parent_post=requested_post,
                likes=0,
                parent_comment=request.form['parent_comment'],
            )
            the_parent_comment = Comment.query.get(new_reply.parent_comment)
            new_reply.parent_chain=the_parent_comment.parent_chain + f"{the_parent_comment.id};"
            db.session.add(new_reply)
            new = Comment.query.filter(Comment.body == new_reply.body).order_by(Comment.id.desc()).first()
            like_comment_on_post(new)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id, _anchor=f'comment_marker_{new_reply.id}'))
    return render_template("post.html", post=requested_post, user=current_user,
                           logged_in=current_user.is_authenticated, form=form, page="Blog",
                           replyform=replyform, year=date.today().year,
                           comments=construct)

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
                           year=date.today().year, user=current_user, page="New Project")


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
        if 'file' not in request.files:
            pass
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
        if edit_form.cover_photo.data == '':
            option_result = f'static/uploads/{filename}'
        else:
            option_result = edit_form.cover_photo.data
        project.title = edit_form.title.data
        project.subtitle = edit_form.subtitle.data
        project.cover_photo = option_result
        project.author = current_user
        project.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_project", proj_id=project.id))
    return render_template('new_project.html', form=edit_form, logged_in=current_user.is_authenticated,
                           year=date.today().year, user=current_user, page="Edit Project")


@app.route("/project/<int:proj_id>", methods=['GET', 'POST'])
def show_project(proj_id):
    form = CommentForm()
    replyform = CommentReplyForm()
    requested_project = Project.query.get(proj_id)
    comment_structure = order_comments_project(proj_id)
    construct = ''
    for n in range(0, len(comment_structure)):
        parent_node = HTML_comment_constructor(comment_structure[n]['comment'])
        parent_HTML = Markup(f'''</ul><ul class="commentList"><li style="margin-left:10vw;margin-right:10vw;list-style:none;"><hr><div>{parent_node}</div></li>''')
        rest_of_node = reducer(comment_structure[n],'',1)
        full_node = parent_HTML+rest_of_node
        construct+=full_node
    if request.method == 'POST':
        if request.form.get('submit')=='Post':
            new_comment = Comment(
                body=request.form['comment'],
                author=current_user,
                parent_project=requested_project,
                likes=0,
                parent_comment=None,
                parent_chain="",
            )
            db.session.add(new_comment)
            new = Comment.query.filter(Comment.body == new_comment.body).order_by(Comment.id.desc()).first()
            like_comment_on_post(new)
            db.session.commit()
            return redirect(url_for('show_project', proj_id=proj_id, _anchor=f'comment_marker_{new_comment.id}'))
        elif request.form.get('reply_submit')=='Post Reply':
            new_reply = Comment(
                body=request.form['comment_reply'],
                author=current_user,
                parent_project=requested_project,
                likes=0,
                parent_comment=request.form['parent_comment'],
            )
            the_parent_comment = Comment.query.get(new_reply.parent_comment)
            new_reply.parent_chain = the_parent_comment.parent_chain + f"{the_parent_comment.id};"
            db.session.add(new_reply)
            new = Comment.query.filter(Comment.body == new_reply.body).order_by(Comment.id.desc()).first()
            like_comment_on_post(new)
            db.session.commit()
            return redirect(url_for('show_project', proj_id=proj_id, _anchor=f'comment_marker_{new_reply.id}'))
    return render_template("project.html", proj=requested_project, user=current_user,
                           logged_in=current_user.is_authenticated, form=form, page="Projects",
                           replyform=replyform, year=date.today().year,
                           comments=construct)

@app.route("/_deletepo/<int:post_id>", methods=['GET', 'POST', 'DELETE'])
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    comments_of_post = post_to_delete.comments
    for comment in comments_of_post:
        db.session.delete(comment)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('blog', logged_in=current_user.is_authenticated,
                            doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user))


@app.route("/_deletepj/<int:proj_id>", methods=['GET', 'POST', 'DELETE'])
@admin_only
def delete_project(proj_id):
    proj_to_delete = Project.query.get(proj_id)
    comments_of_proj = proj_to_delete.comments
    for comment in comments_of_proj:
        db.session.delete(comment)
    db.session.delete(proj_to_delete)
    db.session.commit()
    return redirect(url_for('projects', logged_in=current_user.is_authenticated,
                            doy=datetime.now().timetuple().tm_yday, year=date.today().year, user=current_user))


@app.route("/_deleteco/<int:comment_id>", methods=['GET', 'POST', 'DELETE'])
@login_required
def delete_comment(comment_id):
    comment_to_delete = Comment.query.get(comment_id)
    if comment_to_delete.author.id != 1 and current_user.id == 1:
        comment_to_delete.body = "[Comment Deleted by Admin]"
    else:
        comment_to_delete.body = "[Comment Deleted by Author]"
    db.session.commit()
    if comment_to_delete.post_id == None:
        return redirect(url_for('show_project', proj_id=comment_to_delete.project_id, _anchor=f'comment_marker_{comment_id}'))
    else:
        return redirect(url_for('show_post', post_id=comment_to_delete.post_id, _anchor=f'comment_marker_{comment_id}'))

@app.route("/_deletepp/<int:user_id>/", methods=['GET', 'POST', 'DELETE'])
@login_required
def delete_profile_pic(user_id):
    user_to_delete_from = User.query.get(user_id)
    user_to_delete_from.profile_picture = None
    db.session.commit()
    return redirect(url_for('settings'))

@app.route("/like_comment/<int:comment_id>", methods=['GET', 'POST'])
@login_required
def like_comment(comment_id):
    comment_to_like = Comment.query.get(comment_id)
    comment_to_like.likes+=1
    user_liked_comments = string_to_list(current_user.liked_comments)
    if user_liked_comments == None:
        user_liked_comments = [comment_to_like.id]
    else:
        user_liked_comments.append(comment_to_like.id)
    new_string = list_to_string(user_liked_comments)
    current_user.liked_comments = new_string
    db.session.commit()
    return "success"

@app.route("/unlike_comment/<int:comment_id>", methods=['GET', 'POST'])
@login_required
def unlike_comment(comment_id):
    comment_to_unlike = Comment.query.get(comment_id)
    comment_to_unlike.likes-=1
    user_liked_comments = string_to_list(current_user.liked_comments)
    user_liked_comments = [comment for comment in user_liked_comments if comment!=str(comment_id)]
    current_user.liked_comments = list_to_string(user_liked_comments)
    db.session.commit()
    return "success"

def list_to_string(list):
    if list == None:
        return None
    else:
        string = ""
        for id in list:
            string+=str(id)+";"
        return string

def string_to_list(string):
    list = string.split(";")
    for entry in list:
        if entry == '':
            list.remove(entry)
    return list

def hide_reply_insert(comment_id):
    if Comment.query.get(comment_id).post_id == None:
        all_comments = Comment.query.filter(Comment.project_id==Comment.query.get(comment_id).project_id)
    else:
        all_comments = Comment.query.filter(Comment.post_id==Comment.query.get(comment_id).post_id)
    comments_to_hide = []
    for comment in all_comments:
        this_comment_parent_chain = comment.parent_chain
        listed = string_to_list(this_comment_parent_chain)
        for x in listed:
            if int(x) == comment_id:
                comments_to_hide.append(comment.id)
    return list_to_string(comments_to_hide)


def order_comments(post_id):
    comments = Comment.query.filter(Comment.post_id==post_id)
    comment_tree = []
    for comment in comments:
        if comment.parent_comment == None:
            comment_tree.append(find_children(comment))
    return comment_tree

def order_comments_project(proj_id):
    comments = Comment.query.filter(Comment.project_id==proj_id)
    comment_tree = []
    for comment in comments:
        if comment.parent_comment == None:
            comment_tree.append(find_children(comment))
    return comment_tree

def find_children(comment):
    children = Comment.query.filter(Comment.parent_comment == comment.id)
    if children.count()>0:
        child_list=[]
        for child in children:
            child_list.append(find_children(child))
        return { 'comment' : comment, 'children': child_list }
    else:
        return { 'comment': comment }

def reducer(comments, children_construct,n):
    try:
        for children in comments['children']:
            if len(children)>1:
                this_top = children['comment']
                this_top_HTML = HTML_comment_constructor(this_top)
                styled = Markup(f'''<li style="margin-left:{10+(n*4)}vw;margin-right:10vw;"><div class="vl">{this_top_HTML}</div></li>''')
                children_construct +=styled
                try:
                    if children['children'][0]['comment']:
                        for x in range(0, len(children['children'])):
                            this_grand = HTML_comment_constructor(children['children'][x]['comment'])
                            styled = Markup(f'''<li style="margin-left:{10 + ((n+1) * 4)}vw;margin-right:10vw;"><div class="vl">{this_grand}</div></li>''')
                            children_construct += styled
                            children_construct += reducer(children['children'][x], '', n + 2)
                except:
                    pass
            else:
                #end leaf
                end_leaf = children['comment']
                end_leaf_HTML = HTML_comment_constructor(end_leaf)
                styled = Markup(f'''<li style="margin-left:{10+(n*4)}vw;margin-right:10vw;"><div class="vl">{end_leaf_HTML}</div></li>''')
                children_construct += styled
    except:
        pass
    return children_construct

def HTML_comment_constructor(comment):
    html_starter = Markup(f'''<div id="visibility_tag_{comment.id}" class="visible" style="margin-bottom:2em"><div class='anchor' id=comment_marker_{comment.id}></div>{ comment.body }''')
    like_counter_module = Markup(f'''<div class="row col-5 col-lg-4" ><div class="col-8 col-lg-4" style="color:#F2A900" id="like_counter{comment.id}">+ { comment.likes } likes</div>''')
    if current_user.is_authenticated:
        # set like button class based on if user has liked the comment
        like_check = False
        user_liked_comments = string_to_list(current_user.liked_comments)
        for comment_id in user_liked_comments:
            if comment_id == str(comment.id):
                like_check = True
        if like_check == False:
            like_button_module = Markup(f'''<div class="col-2" style="margin-left:-1em"><div class="hvr-float-shadow"><a class="icon fa-thumbs-up" onclick="changeText({comment.id})" id="button_marker{comment.id}"></a></div></div>''')
        else:
            like_button_module = Markup(f'''<div class="col-2" style="margin-left:-1em"><div class="hvr-float-shadow"><a class="icon solid fa-thumbs-up" style="color:#F2A900;" onclick="changeText({comment.id})" id="button_marker{comment.id}"></a></div></div>''')
        reply_module = Markup(f'''<div class="col-2"><div class="hvr-float-shadow"><a class="icon solid fa-reply" style="color:white;" id=reply_button{comment.id} onclick="showReplyBox( {comment.id} )"></a></div></div></div>''')
    else:
        like_button_module = Markup(
            f'''<div class="col-2" style="margin-left:-1em"><div class="hvr-float-shadow"><a class="icon fa-thumbs-up" tabindex="{comment.id*10}" style="color:gray;" id="button_marker{comment.id}" data-bs-toggle="popover" data-bs-placement="left" data-bs-trigger="focus" data-bs-content="Log in to Like"></a></div></div>''')
        reply_module = Markup(f'''<div class="col-2"><div class="hvr-float-shadow"><a class="icon solid fa-reply" tabindex="{(comment.id*10)+1}" style="color:gray;" id=reply_button{comment.id}" data-bs-toggle="popover" data-bs-placement="right" data-bs-trigger="focus" data-bs-content="Log in to Reply"></a></div></div></div>''')
    modules = like_counter_module+like_button_module+reply_module
    delete_module = Markup(f'''<div class="row col-sm-8 col-lg-4" ><div class="col-2"><div class="hvr-grow"><a href="{url_for('delete_comment', comment_id=comment.id) }" class="icon fa-trash-alt" style="color:gray;padding-left:0.5em;"></a></div></div>''')
    try:
        if current_user == comment.author or current_user.id == 1:
            modules+=delete_module
    except:
        pass
    this_comment_children = hide_reply_insert(comment.id)
    try:
        if current_user.id == comment.author.id or current_user.id == 1:
            hide_replies_button = Markup(f'''<div class="col-4 col-sm-6""><div class="hvr-grow"><a class="icon solid fa-eye" style="color:white" onclick="handleReplyVisibility({comment.id})" id="hide_reply{comment.id}" value="{this_comment_children}"> Hide Replies</a></div></div></div>''')
    except:
        hide_replies_button = Markup(f'''<div class="row col-sm-5 col-lg-4"><div class="col-4 col-sm-6""><div class="hvr-grow"><a class="icon solid fa-eye" style="color:white;margin-left:7px" onclick="handleReplyVisibility({comment.id})" id="hide_reply{comment.id}" value="{this_comment_children}"> Hide Replies</a></div></div></div>''')
    html_starter+=modules+hide_replies_button
    if comment.author == None:
        deleted_commenter = Markup('<div>[User Account Deleted]</div>')
        html_with_commenter = html_starter+deleted_commenter
    else:
        intact_commenter_image = Markup('<div class="accountImage me-auto">')
        if comment.author.profile_picture==None:
            gravatar = gravatar_gen(comment.author.email)
            intact_commenter_image+=Markup(f'''<img src="{gravatar}"/><br></div>''')
        else:
            intact_commenter_image+=Markup(f'''<img src="../{ comment.author.profile_picture }" class="accountImageCropped"/><br></div>''')
        html_with_commenter_image = html_starter+intact_commenter_image
        commenter = Markup(f'''<a href="{ url_for('user_page', user_id=comment.author.id) }" class="user-link">- @{ comment.author.name }</a>''')
        html_with_commenter = html_with_commenter_image + commenter
    replyform = CommentReplyForm()
    comment_reply_box = Markup(f'''</div></div><div class="justify-content-center" style="border-left:none"><form class="needs-validation" style="display:none;" id="{comment.id}" action="" method="post" novalidate>{ replyform.csrf_token() }{ replyform.parent_comment(value=comment.id) }<div class="col-lg-8"><div class="form-group">Reply to @{comment.author.name}<textarea class="form-control" name="comment_reply" rows="3" style="color:white;background-color:rgba(27, 31, 34, 0.85)" required></textarea><div class="invalid-feedback">Please include a message.</div></div><br></div><div class="col-3">{ replyform.reply_submit(class_="btn btn-dark") }</div></form></div>''')
    comment_with_reply=html_with_commenter+comment_reply_box
    return comment_with_reply


def send_contact_email(name, email, message):
    configuration = sib_api_v3_sdk.Configuration()
    load_dotenv(find_dotenv())
    KEY = os.environ["SENDINBLUE_KEY"]

    configuration.api_key['api-key'] = KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    subject = 'Website Contact Request'
    html_content = f'name: {name}<br>email: {email}<br>message: {message}'
    sender = {"name": "Michael Freno", "email": 'michael@freno.me'}
    to = [{"email": 'michaelt.freno@gmail.com', "name": "Michael Freno"}]
    cc = [{"email": "michael@freno.me", "name": "Michael Freno"}]
    reply_to = {"name": "Michael Freno", "email": 'michael@freno.me',}
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to,  cc=cc, reply_to=reply_to,
                                                   html_content=html_content, sender=sender, subject=subject)

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(api_response)
    except ApiException as e:
        print("Exception when calling SMTPApi->send_transac_email: %s\n" % e)

def like_comment_on_post(comment):
    comment.likes+=1
    user_liked_comments = string_to_list(current_user.liked_comments)
    if user_liked_comments == None:
        user_liked_comments = [comment.id]
    else:
        user_liked_comments.append(comment.id)
    new_string = list_to_string(user_liked_comments)
    current_user.liked_comments = new_string


def send_registration_email(name, email):
    configuration = sib_api_v3_sdk.Configuration()
    load_dotenv(find_dotenv())
    KEY = os.environ["SENDINBLUE_KEY"]
    configuration.api_key['api-key'] = KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    subject = 'Thank you!'
    sender = {"name": "Michael Freno", "email": 'michael@freno.me'}
    reply_to = {"name": "Michael Freno", "email": 'michael@freno.me'}
    templateId = 1
    params = {'FIRSTNAME': name}
    to = [{"email": email, "name": name}]
    attachment = [{"content":f"{image}",
                   "name":"logo.jpg"}]
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, reply_to=reply_to, attachment=attachment,
                                                   template_id=templateId, params=params, sender=sender, subject=subject)
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(api_response)
    except ApiException as e:
        print("Exception when calling SMTPApi->send_transac_email: %s\n" % e)

def gravatar_gen(email):
    g = G(email)
    return g.get_image(size=100,default='identicon')



if __name__ == '__main__':
    from waitress import serve
    print("Running at")
    this_port = "8080"
    print(f"http://localhost:{this_port}/ http://127.0.0.1:{this_port}")
    server_port = os.environ.get('PORT', this_port)
    serve(app, host="0.0.0.0", port=server_port)
