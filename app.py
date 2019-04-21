from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__, static_folder='templates/static')
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="root",
                             db="Finstagram",
                             charset="utf8mb4",
                             port=8889,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    query2 = "SELECT followerUsername FROM Follow WHERE acceptedFollow = %s AND followeeUsername = %s"
    followee = session["username"]
    with connection.cursor() as cursor2:
        cursor2.execute(query2, (0, followee))
    requests = cursor2.fetchall()
    # print(requests)
    return render_template("home.html", username=session["username"], requests=requests)

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")


@app.route("/notifications", methods=["GET"])
@login_required
def notifications():
    getQuery = "SELECT followerUsername FROM Follow WHERE acceptedFollow=%s AND followeeUsername=%s"
    followee = session["username"]
    with connection.cursor() as cursor:
        cursor.execute(getQuery, (0, followee))
    followerRequests = cursor.fetchall()
    # print(followerRequests)
    query = "SELECT * FROM Tag NATURAL JOIN Photo WHERE (username=%s AND acceptedTag=%s)"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], 0))
    data = cursor.fetchall()
    return render_template("notifications.html", taggedNotifications=data, followerRequests=followerRequests)


# AllFollowers: True
#     - (Your followers) + (all members in groups you own can see) + (YOU)
# AllFollowers: False
#     - (YOU) + (all members in groups you own can see)

@app.route("/images", methods=["GET", "POST"])
@login_required
def images():
    user = session["username"]
    cursor = connection.cursor()
    queryFollow = "CREATE VIEW myfollows AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo JOIN Follow ON (Photo.photoOwner=followeeUsername) WHERE followerUsername=%s AND allFollowers=%s"
    cursor.execute(queryFollow, (user, 1))
    cursor.close()

    cursor = connection.cursor()
    queryGroups = "CREATE VIEW mygroups AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo NATURAL JOIN Belong WHERE Belong.username=%s"
    cursor.execute(queryGroups, (user))
    cursor.close()

    cursor = connection.cursor()
    querySelf = "CREATE VIEW myphotos AS SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
    cursor.execute(querySelf, (user))
    cursor.close()

    cursor = connection.cursor()
    totalQuery = "SELECT DISTINCT photoID, timestamp, filePath, caption, photoOwner FROM mygroups UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myphotos) UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myfollows) ORDER BY timestamp DESC"
    cursor.execute(totalQuery)
    data = cursor.fetchall()
    # print(data)
    cursor.close()

    cursor = connection.cursor()
    query = "DROP VIEW myphotos, mygroups, myfollows"
    cursor.execute(query)
    cursor.close()

    cursor = connection.cursor()
    taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
    cursor.execute(taggedquery)
    taggedUsers = cursor.fetchall()
    cursor.close()

    return render_template("images.html", photos=data, taggedUsers=taggedUsers)

@app.route("/groups", methods=["GET"])
def groups():
    groupOwner = session["username"]
    query1 = "SELECT * FROM CloseFriendGroup WHERE groupOwner=%s"
    query2 = "SELECT * FROM Belong WHERE groupOwner=%s"
    with connection.cursor() as cursor1:
        cursor1.execute(query1, (groupOwner))
    with connection.cursor() as cursor2:
        cursor2.execute(query2, (groupOwner))
    data1 = cursor1.fetchall()
    data2 = cursor2.fetchall()
    # print(data2)
    return render_template("groups.html", groups=data1, users=data2, username=session["username"])


@app.route("/searchPhoto", methods=["POST"])
def searchPhoto():
    user = session["username"]
    searchPhoto = request.form["getphoto"]

    cursor = connection.cursor()
    queryFollow = "CREATE VIEW myfollows AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo JOIN Follow ON (Photo.photoOwner=followeeUsername) WHERE followerUsername=%s AND allFollowers=%s"
    cursor.execute(queryFollow, (user, 1))
    cursor.close()

    cursor = connection.cursor()
    queryGroups = "CREATE VIEW mygroups AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo NATURAL JOIN Belong WHERE Belong.username=%s"
    cursor.execute(queryGroups, (user))
    cursor.close()

    cursor = connection.cursor()
    querySelf = "CREATE VIEW myphotos AS SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
    cursor.execute(querySelf, (user))
    cursor.close()

    cursor = connection.cursor()
    totalQuery = "CREATE VIEW gallery AS SELECT DISTINCT photoID, timestamp, filePath, caption, photoOwner FROM mygroups UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myphotos) UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myfollows) ORDER BY timestamp DESC"
    cursor.execute(totalQuery)
    cursor.close()

    cursor = connection.cursor()
    searchQuery = "SELECT * FROM gallery WHERE photoID=%s"
    cursor.execute(searchQuery, (searchPhoto))
    data = cursor.fetchall()

    cursor = connection.cursor()
    query = "DROP VIEW myphotos, mygroups, myfollows, gallery"
    cursor.execute(query)
    cursor.close()

    cursor = connection.cursor()
    taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
    cursor.execute(taggedquery)
    taggedUsers = cursor.fetchall()
    cursor.close()

    return render_template("images.html", username=session["username"], currPhoto=data, taggedUsers=taggedUsers)


@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")


@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.files:
        image_file = request.files.get("profilePic", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)

        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        bio = requestData["bio"]
        private = requestData["private"]
        if (private=="yes"):
            private = 1
        else:
            private = 0
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname, avatar, bio, isPrivate) VALUES (%s, %s, %s, %s, %s, %s, %r)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, image_name, bio, private))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")


@app.route("/uploadImage", methods=["GET", "POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        caption = request.form["caption"]
        imageOwner = session["username"]
        taggedUser = request.form["taggedUser"]
        if (len(taggedUser) != 0):
            taggedUser = taggedUser.split(',')
        else:
            taggedUser = ""
        test = request.form.get("allFollowers")
        if (test == "on"):
            allFollowers = True
        else:
            allFollowers = False
        query1 = "INSERT INTO photo (timestamp, filePath, caption, allFollowers, photoOwner) VALUES (%s, %s, %s, %s, %s)"

        with connection.cursor() as cursor1:
            cursor1.execute(query1, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, caption, allFollowers, imageOwner))
        if (taggedUser != ""):
            try:
                with connection.cursor() as cursor2:
                    query2 = "INSERT INTO Tag (username, photoID, acceptedTag) VALUES (%s, %s, %r)"
                    query3 = "SELECT username FROM Belong WHERE groupOwner = %s AND username = %s"
                    for taggee in taggedUser:
                        if (taggee==imageOwner):
                            cursor2.execute(query2, (taggee, cursor1.lastrowid, True))
                        elif (taggee != imageOwner):
                            if (allFollowers==True):
                                cursor2.execute(query2, (taggee, cursor1.lastrowid, False))
                            else:
                                cursor2.execute(query3, (imageOwner, taggee))
                                data = cursor2.fetchone()
                                if data:
                                    cursor2.execute(query2, (taggee, cursor1.lastrowid, False))
                                else:
                                    error = "Tagged user cannot view photo, invalid tag"
                                    return render_template('upload.html', error=error, username=session["username"])
            except pymysql.err.IntegrityError:
                error = "Tagged user(s) do not exist. Please try again."
                return render_template('upload.html', error=error, username=session["username"])

        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message, username=session["username"])

    error = "Failed to upload image."
    return render_template("upload.html", error=error, username=session["username"])


@app.route("/taggedStatus", methods=["POST"])
@login_required
def taggedStatus():
    if request.form:
        # print(request.form['status'])
        # print(request.form['submit_button'])
        getQuery = "SELECT photoID FROM TAG WHERE (username=%s AND acceptedTag=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (session["username"], 0))
        data = cursor.fetchall()
        # print(data)
        currUser = session["username"]
        for photo in data:
            # print('status' + str(photo['photoID']))
            currStatus = request.form.get('status' + str(photo['photoID']))
            if (currStatus == "accept"):
                statusFlag = True
                queryT = "UPDATE Tag SET acceptedTag=%r WHERE (username=%s AND photoID=%s)"
                with connection.cursor() as cursor1:
                    cursor1.execute(queryT, (statusFlag, currUser, photo['photoID']))
            elif (currStatus == "decline"):
                queryF = "DELETE FROM Tag WHERE (username=%s AND photoID=%s)"
                with connection.cursor() as cursor2:
                    cursor2.execute(queryF, (currUser, photo['photoID']))
            else:
                continue
    return redirect(url_for('notifications'))


@app.route("/createGroup", methods=["POST"])
def createGroup():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        groupOwner = session["username"]
        query = "INSERT INTO CloseFriendGroup (groupName, groupOwner) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (groupName, groupOwner))
        message = "CloseFriendGroup has been successfully created."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to create CloseFriendGroup."
        return render_template("groups.html", message=message, username=session["username"])

@app.route("/addMember", methods=["POST"])
def addMember():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        newMember = requestData["newMember"]
        owner = session["username"]
        try:
            query = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                cursor.execute(query, (groupName, owner, newMember))
            message = newMember + " has successfully been added to " + groupName
        except:
            message = "User is already in this closeFriendGroup..."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to add " + newMember + " to " + groupName
        return render_template("groups.html", message=message, username=session["username"])


@app.route("/follow", methods=["POST"])
def follow():
    if request.form:
        requestData = request.form
        followee = requestData["followee"]
        follower = session["username"]
        acceptedFollow = 0

        try:
            query = "INSERT INTO Follow (followerUsername, followeeUsername, acceptedFollow) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                if follower != followee:
                    cursor.execute(query, (follower, followee, acceptedFollow))
                    message = "Follower request sent to " + followee
                else:
                    message = "You can't follow yourself!"
        except:
            message = "Failed to request follow for " + followee
        return render_template("home.html", message=message, username=session["username"])
    else:
        return render_template("home.html", username=session["username"])

@app.route("/unfollow", methods=["POST"])
def unfollow():
    if request.form:
        requestData = request.form
        unfollowee = requestData["unfollowee"]
        follower = session["username"]
        try:
            deleteQuery = "DELETE FROM Follow WHERE followeeUsername=%s AND followerUsername=%s"
            with connection.cursor() as cursor:
                cursor.execute(deleteQuery, (unfollowee, follower))
        except:
            # error message still not right -- will leave like this for now
            message = "Unfollowed " + unfollowee
        return render_template("followers.html", message=message, username=session["username"])
    else:
        return render_template("followers.html", message=message, username=session["username"])

@app.route("/followers", methods=["GET"])
def followers():
    user = session["username"]
    query1 = "SELECT followerUsername FROM Follow WHERE followeeUsername=%s AND acceptedfollow=%s"
    query2 = "SELECT followeeUsername FROM Follow WHERE followerUsername=%s AND acceptedfollow=%s"
    with connection.cursor() as cursor1:
        cursor1.execute(query1, (user, 1))
    with connection.cursor() as cursor2:
        cursor2.execute(query2, (user, 1))

    followers = cursor1.fetchall()
    following = cursor2.fetchall()
    # print(data2)
    return render_template("followers.html", followers=followers, following=following, username=session["username"])


@app.route("/followStatus", methods=["POST"])
@login_required
def followStatus():
    if request.form:
        followee = session["username"]
        getQuery = "SELECT followerUsername FROM Follow WHERE (followeeUsername=%s AND acceptedfollow=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (followee, 0))
        data = cursor.fetchall()
        # print(data)
        for follower in data:
            currStatus = request.form["status" + follower["followerUsername"]]
            if currStatus == "accept":
                updateQuery = "UPDATE Follow SET acceptedFollow=%s WHERE followeeUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(updateQuery, (1, followee))
            else:
                deleteQ = "DELETE FROM Follow WHERE followerUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(deleteQ, (follower["followerUsername"]))
    return render_template("notifications.html", username=session["username"])


if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
