from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor, CKEditorField
from datetime import date, datetime
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from functools import wraps
from sqlalchemy.exc import IntegrityError
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import *
from image_var import image
from markupsafe import Markup
import json

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PP_UPLOAD_FOLDER = 'static/uploads/profile_pictures'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000
app.config['PP_FOLDER'] = PP_UPLOAD_FOLDER

ckeditor = CKEditor(app)
Bootstrap(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///site.db").replace("postgres://",
                                                                                                    "postgresql://", 1)
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
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"))
    parent_comment = db.Column(db.Integer, nullable=True)
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
                    name=nameFix
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
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.cover_photo.data
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
        parent_node = HTML_comment_pass(comment_structure[n]['comment'])
        parent_HTML = Markup(f'''</ul><ul class="commentList"><li style="margin-left:10vw;margin-right:10vw;list-style:none;"><hr><div>{parent_node}</div></li><br>''')
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
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id, _anchor="past_last"))
        elif request.form.get('reply_submit')=='Post Reply':
            new_reply = Comment(
                body=request.form['comment_reply'],
                author=current_user,
                parent_post=requested_post,
                likes=0,
                parent_comment=request.form['parent_comment'],
            )
            db.session.add(new_reply)
            db.session.commit()
            return redirect(url_for('show_post', post_id=post_id, _anchor="past_last"))
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
        project.title = edit_form.title.data
        project.subtitle = edit_form.subtitle.data
        project.cover_photo = edit_form.cover_photo.data
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
        parent_node = HTML_comment_pass(comment_structure[n]['comment'])
        parent_HTML = Markup(f'''</ul><ul class="commentList"><li style="margin-left:10vw;margin-right:10vw;list-style:none;"><hr><div>{parent_node}</div></li><br>''')
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
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for('show_project', proj_id=proj_id, _anchor="past_last"))
        elif request.form.get('reply_submit')=='Post Reply':
            new_reply = Comment(
                body=request.form['comment_reply'],
                author=current_user,
                parent_project=requested_project,
                likes=0,
                parent_comment=request.form['parent_comment'],
            )
            db.session.add(new_reply)
            db.session.commit()
            return redirect(url_for('show_project', proj_id=proj_id, _anchor="past_last"))
    return render_template("project.html", proj=requested_project, user=current_user,
                           logged_in=current_user.is_authenticated, form=form, page="Projects",
                           replyform=replyform, year=date.today().year,
                           comments=construct)


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
                this_top_HTML = HTML_comment_pass(this_top)
                styled = Markup(f'''<li style="margin-left:{10+(n*4)}vw;margin-right:10vw;"><div class="vl">{this_top_HTML}</div></li><br>''')
                children_construct +=styled
                grandchild_fix = HTML_comment_pass(children['children'][0]['comment'])
                styled = Markup(f'''<li style="margin-left:{10+((n+1)*4)}vw;margin-right:10vw;"><div class="vl">{grandchild_fix}</div></li><br>''')
                children_construct+=styled
                children_construct+=reducer(children['children'][0],'',n+1)
                #this is an ugly fix
                try:
                    if children['children'][1]['comment']:
                        for x in range(1, len(children['children'])):
                            print(children['children'][x]['comment'])
                            this_grand = HTML_comment_pass(children['children'][x]['comment'])
                            styled = Markup(f'''<li style="margin-left:{10 + ((n+1) * 4)}vw;margin-right:10vw;"><div class="vl">{this_grand}</div></li><br>''')
                            children_construct += styled
                            children_construct += reducer(children['children'][x], '', n + 2)
                except:
                    pass
            else:
                #end leaf
                end_leaf = children['comment']
                end_leaf_HTML = HTML_comment_pass(end_leaf)
                styled = Markup(f'''<li style="margin-left:{10+(n*4)}vw;margin-right:10vw;"><div class="vl">{end_leaf_HTML}</div></li><br>''')
                children_construct += styled
    except:
        pass
    return children_construct


def HTML_comment_pass(comment):
    html_starter = Markup(f'''<p>{ comment.body }</p>''')
    if comment.author == None:
        deleted_commenter = Markup('<div>[User Account Deleted]</div>')
        html_with_commenter = html_starter+deleted_commenter
    else:
        intact_commenter_image = Markup('<div class="accountImage me-auto">')
        if comment.author.profile_picture==None:
            intact_commenter_image+=Markup('''<img src="{{ '''+ f'''{comment.author.email}''' + ''' | gravatar }}"/><br></div>''')
        else:
            intact_commenter_image+=Markup(f'''<img src="../{ comment.author.profile_picture }" class="accountImageCropped"/><br></div>''')
        html_with_commenter_image = html_starter+intact_commenter_image
        commenter = Markup(f'''<a href="{ url_for('user_page', user_id=comment.author.id) }">''' + f'''<span class="date sub-text">- @{ comment.author.name }</span></a>''')
        html_with_commenter = html_with_commenter_image + commenter
    modules = Markup(f'''<div class="row"><div class="col-3"><div class="like_button_container" data-commentid="{comment.id}"></div></div><div class="col-3"><button class="icon solid fa-reply" style="color:gray;margin-left:0.5em;" onclick="showReplyBox( {comment.id} )"></button></div></div>''')
    full_comment_node = html_with_commenter+ modules
    replyform = CommentReplyForm()
    comment_reply_box = Markup(f'''</div><div class="justify-content-center" style="border-left:none"><form class="needs-validation" style="display:none;" id="{comment.id}" action="" method="post" novalidate>{ replyform.csrf_token() }{ replyform.parent_comment(value=comment.id) }<div class="col-lg-8"><div class="form-group">{ replyform.body.label }<textarea class="form-control" name="comment_reply" rows="3" style="color:white;background-color:rgba(27, 31, 34, 0.85)" required></textarea><div class="invalid-feedback">Please include a message.</div></div><br></div><div class="col-3">{ replyform.reply_submit(class_="btn btn-dark") }</div></form></div>''')
    comment_with_reply=full_comment_node+comment_reply_box
    return comment_with_reply


def send_contact_email(name, email, message):
    message = Mail(
        from_email='michael@freno.me',
        to_emails='michaelt.freno@gmail.com',
        subject='Website Contact Request',
        html_content=f'name: {name}<br>email: {email}<br>message: {message}')
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e)


def send_registration_email(name, email):
    message = Mail(
        from_email='michael@freno.me',
        to_emails=email,
        subject='Thank you!',
        html_content=f'<h4 style="text-align: center;"><img src="data:image/jpeg;base64,{image}"'
                     f'alt="logo" style="height:50px;width:50px">Mike Freno</h4><br><h2>Hello {name},<br> Thanks for registering for my website!</h2><br> '
                     f'No other emails will be sent to you, '
                     f' outside of responses back for inquiry and any emailers that you decide to opt-in to (yet to be '
                     f'implemented as of writing), of which you can of course opt out of at anytime. <br><br> Thanks '
                     f'again!<br><br> -Michael Freno')
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e.message)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 4000)))



# {'comment': <Comment 1>, 'children': [{'comment': <Comment 2>, 'children': [{'comment': <Comment 3>, 'children': [{'comment': <Comment 8>}]}]}, {'comment': <Comment 15>}, {'comment': <Comment 16>}]}
