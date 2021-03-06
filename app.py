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

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/settings", methods=["GET"])
def settings():
    return render_template("settings.html")

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

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

# Required Feature #1: View visible photos and info about them
@app.route("/images", methods=["GET", "POST"])
@login_required
def images():
    user = session["username"]

    # Query for photos of the people you follow
    cursor = connection.cursor()
    queryFollow = "CREATE VIEW myfollows AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo JOIN Follow ON (Photo.photoOwner=followeeUsername) WHERE followerUsername=%s AND allFollowers=%s"
    cursor.execute(queryFollow, (user, 1))
    cursor.close()

    # Query for photos of the people of the close friend groups that you are in
    cursor = connection.cursor()
    queryGroups = "CREATE VIEW mygroups AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo NATURAL JOIN Belong WHERE Belong.username=%s"
    cursor.execute(queryGroups, (user))
    cursor.close()

    # Query for photos that the user posted
    cursor = connection.cursor()
    querySelf = "CREATE VIEW myphotos AS SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
    cursor.execute(querySelf, (user))
    cursor.close()

    # Query that unions the three separate views and returns distinct photos
    cursor = connection.cursor()
    totalQuery = "SELECT DISTINCT photoID, timestamp, filePath, caption, photoOwner FROM mygroups UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myphotos) UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myfollows) ORDER BY timestamp DESC"
    cursor.execute(totalQuery)
    data = cursor.fetchall()
    # print(data)
    cursor.close()

    # Query that drops the created views
    cursor = connection.cursor()
    query = "DROP VIEW myphotos, mygroups, myfollows"
    cursor.execute(query)
    cursor.close()

    # Query for getting all the tagged users of the photos
    cursor = connection.cursor()
    taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
    cursor.execute(taggedquery)
    taggedUsers = cursor.fetchall()
    cursor.close()

    # Query for getting comments of photos
    cursor = connection.cursor()
    commentsQuery = "SELECT username, photoID, commentText FROM Comment"
    cursor.execute(commentsQuery)
    comments = cursor.fetchall()
    cursor.close()

    # Query for getting likes of photos
    cursor = connection.cursor()
    likesQuery = "SELECT username, photoID FROM Liked"
    cursor.execute(likesQuery)
    likes = cursor.fetchall()
    cursor.close()

    return render_template("images.html", photos=data, taggedUsers=taggedUsers, comments=comments, likes=likes)

# Required Feature #6: Add friend
# Responsible for getting information from the database to show the close friend groups of a user
@app.route("/groups", methods=["GET"])
@login_required
def groups():
    groupOwner = session["username"]
    # Queries that check the close friend groups the user owns or belongs to
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

# Required Feature #5: Tag a photo
@app.route("/tagAUser", methods=["GET","POST"])
@login_required
def tagAUser():
    if request.form:
        requestData = request.form
        photoID = ''
        taggedUser = ''
        user = session["username"]
        for name in requestData:
            photoID = name.strip("tagUser")
            taggedUser = requestData[name]
        if (len(taggedUser) != 0):
            taggedUser = taggedUser.split(',')
        else:
            taggedUser = ""

        if request.method == "POST":
            check = "SELECT * FROM tag WHERE photoID=%s AND username=%s"
            if (taggedUser != ""):
                try:
                    with connection.cursor() as cursor:
                        # Same queries used to find the photos that can be viewed by the person being tagged
                        queryFollow = "CREATE VIEW myfollows AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo JOIN Follow ON (Photo.photoOwner=followeeUsername) WHERE followerUsername=%s AND allFollowers=%s"
                        queryGroups = "CREATE VIEW mygroups AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo NATURAL JOIN Belong WHERE Belong.username=%s"
                        querySelf = "CREATE VIEW myphotos AS SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
                        totalQuery = "SELECT DISTINCT photoID, timestamp, filePath, caption, photoOwner FROM mygroups UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myphotos) UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myfollows) ORDER BY timestamp DESC"
                        query = "DROP VIEW myphotos, mygroups, myfollows"

                        for taggee in taggedUser:
                            cursor.execute(queryFollow, (taggee, 1))
                            cursor.execute(queryGroups, (taggee))
                            cursor.execute(querySelf, (taggee))
                            cursor.execute(totalQuery)
                            data = cursor.fetchone()
                            cursor.execute(query)
                            # if the tagge cannot view the photo
                            if not data:
                                message = "Photo isn't visible to the taggee"
                                return render_template("images.html", message=message, username=session["username"])
                            cursor.execute(check, (photoID, taggee))
                            data2 = cursor.fetchone()
                            # if the tagge has already been tagged in the photo
                            if data2:
                                message = "Taggee has already been tagged"
                                return render_template("images.html", message=message, username=session["username"])

                            # else, insert a row into the Tage table with the taggee
                            query2 = "INSERT INTO Tag (username, photoID, acceptedTag) VALUES (%s, %s, %r)"
                            query3 = "SELECT username FROM Belong WHERE groupOwner = %s AND username = %s"
                            if (taggee==user):
                                cursor.execute(query2, (taggee, photoID, True))
                            else:
                                cursor.execute(query2, (taggee, photoID, False))
                except pymysql.err.IntegrityError:
                    error = "Tagged user(s) do not exist. Please try again."
                    return render_template('images.html', error=error, username=session["username"])

                message = "Image has been successfully tagged."
                return render_template("images.html", message=message, username=session["username"])

            error = "Failed to tag user."
        return redirect(url_for("images"))

#Extra Feature #10: Search by photo (knowing photoID)
@app.route("/searchPhoto", methods=["POST"])
@login_required
def searchPhoto():
    user = session["username"]
    searchPhoto = request.form["getphoto"]

    # Query for photos of the people you follow
    cursor = connection.cursor()
    queryFollow = "CREATE VIEW myfollows AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo JOIN Follow ON (Photo.photoOwner=followeeUsername) WHERE followerUsername=%s AND allFollowers=%s"
    cursor.execute(queryFollow, (user, 1))
    cursor.close()

    # Query for photos of the people of the close friend groups that you are in
    cursor = connection.cursor()
    queryGroups = "CREATE VIEW mygroups AS SELECT DISTINCT filePath, photoID, timestamp, caption, photoOwner FROM Photo NATURAL JOIN Belong WHERE Belong.username=%s"
    cursor.execute(queryGroups, (user))
    cursor.close()

    # Query for photos that the user posted
    cursor = connection.cursor()
    querySelf = "CREATE VIEW myphotos AS SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
    cursor.execute(querySelf, (user))
    cursor.close()

    # Query that unions the three separate views and returns distinct photos
    cursor = connection.cursor()
    totalQuery = "CREATE VIEW gallery AS SELECT DISTINCT photoID, timestamp, filePath, caption, photoOwner FROM mygroups UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myphotos) UNION (SELECT photoID,timestamp,filePath, caption, photoOwner FROM myfollows) ORDER BY timestamp DESC"
    cursor.execute(totalQuery)
    cursor.close()

    #Query that matches the photoId with the searched photo
    cursor = connection.cursor()
    searchQuery = "SELECT * FROM gallery WHERE photoID=%s"
    cursor.execute(searchQuery, (searchPhoto))
    data = cursor.fetchall()
    if len(data) == 0:
        cursor = connection.cursor()
        query = "DROP VIEW myphotos, mygroups, myfollows, gallery"
        cursor.execute(query)
        cursor.close()

        # Query for photos of the people you follow
        cursor = connection.cursor()
        taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
        cursor.execute(taggedquery)
        taggedUsers = cursor.fetchall()
        cursor.close()
        message = "Photo you are searching for was not found"
        return render_template("images.html", username=session["username"], message=message)

    # Query that drops the created views
    cursor = connection.cursor()
    query = "DROP VIEW myphotos, mygroups, myfollows, gallery"
    cursor.execute(query)
    cursor.close()

    # Query for photos of the people you follow
    cursor = connection.cursor()
    taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
    cursor.execute(taggedquery)
    taggedUsers = cursor.fetchall()
    cursor.close()
    return render_template("images.html", username=session["username"], currPhoto=data, taggedUsers=taggedUsers)


# Login Authentification
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

# Register Authentification
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

    else:
        error = "An error has occurred. Please try again."
        return render_template("register.html", error=error)

# Extra Feature: Update user settings
@app.route("/updateInfo", methods=["POST"])
@login_required
def updateInfo():
    if request.form:
        if request.files:
            image_file = request.files.get("profilePic", "")
            image_name = image_file.filename
            filepath = os.path.join(IMAGES_DIR, image_name)
            image_file.save(filepath)
        else:
            image_name = "default_image.jpg"
        username=session["username"]
        requestData = request.form
        plaintextPasword = requestData["password"]
        confirmPassword = requestData["confirmPassword"]
        # Checks if the new password and confirm password entered by the user, matches
        if (plaintextPasword==confirmPassword):
            hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        else:
            error = "Passwords do not match! Try again!"
            return render_template("settings.html", error=error)
        bio = requestData["bio"]
        private = requestData["private"]
        if (private=="yes"):
            private = 1
        else:
            private = 0
        with connection.cursor() as cursor:
            # Update query that changes the row in the table of the current user
            query = "UPDATE person SET password=%s, avatar=%s, bio=%s, isPrivate=%r WHERE username=%s"
            cursor.execute(query, (hashedPassword, image_name, bio, private, username))

        return redirect(url_for("home"))

    error = "An error has occurred. Please try again."
    return render_template("settings.html", error=error)

# Required Feature #2: Post a photo
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
        followerFlag = request.form.get("allFollowers")
        if (followerFlag == "on"):
            allFollowers = True
        else:
            allFollowers = False
        # Query that inserts the new photo being uploaded into the Photo table
        query1 = "INSERT INTO photo (timestamp, filePath, caption, allFollowers, photoOwner) VALUES (%s, %s, %s, %s, %s)"

        with connection.cursor() as cursor1:
            cursor1.execute(query1, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, caption, allFollowers, imageOwner))
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message, username=session["username"])

    error = "Failed to upload image."
    return render_template("upload.html", error=error, username=session["username"])

# Required Feature #4: Manage tag requests
@app.route("/taggedStatus", methods=["POST"])
@login_required
def taggedStatus():
    if request.form:
        getQuery = "SELECT photoID FROM TAG WHERE (username=%s AND acceptedTag=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (session["username"], 0))
        data = cursor.fetchall()
        currUser = session["username"]
        for photo in data:
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

# Required Feature #6: Add friend
# Used for creating a new close friend group
@app.route("/createGroup", methods=["POST"])
@login_required
def createGroup():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        groupOwner = session["username"]
        # Query used to create a new close friend group
        query = "INSERT INTO CloseFriendGroup (groupName, groupOwner) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (groupName, groupOwner))
        message = "CloseFriendGroup has been successfully created."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to create CloseFriendGroup."
        return render_template("groups.html", message=message, username=session["username"])

# Required Feature #6: Add friend
# Used for adding a new member to a close friend group
@app.route("/addMember", methods=["POST"])
@login_required
def addMember():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        newMember = requestData["newMember"]
        owner = session["username"]
        try:
            # Query for adding a new member to a close friend group
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

# Extra Feature #11: Search by Poster
@app.route("/searchForUser", methods=["POST"])
@login_required
def searchForUser():
    user = session['username']
    if request.form:
        requestData = request.form
        searchedUser = requestData["searchedUser"]
        with connection.cursor() as cursor:
            # Query to check if the current user follows the searched user
            check = "SELECT * FROM Follow WHERE followeeUsername=%s AND followerUsername=%s AND acceptedFollow=1"
            cursor.execute(check, (searchedUser, user))
            checkData = cursor.fetchone()

            # Query to check if the searched user is a private account
            check2 = "SELECT * FROM Person WHERE username=%s AND isPrivate=1"
            cursor.execute(check2, (searchedUser))
            check2Data = cursor.fetchone()

            # Query to check if the searched user exists
            exists = "SELECT * FROM Person WHERE username=%s"
            cursor.execute(exists, (searchedUser))
            existData = cursor.fetchone()

            if existData:
                if (check2Data):
                    if not checkData:
                        message = "You cannot view searched user's photos"
                        return render_template("home.html", message=message, username=session["username"])

                # If the checks are satisfied, then display the searched user's images
                query1 = "SELECT filePath, photoID, timestamp, caption, photoOwner FROM Photo WHERE photoOwner=%s"
                cursor.execute(query1, (searchedUser))
                data = cursor.fetchall()

                # Query that gets the tagged users of the photos
                taggedquery = "SELECT * FROM Tag JOIN Photo ON (Tag.photoID = Photo.photoID) NATURAL JOIN Person"
                cursor.execute(taggedquery)
                taggedUsers = cursor.fetchall()
                cursor.close()
                return render_template("specificUser.html", username=session["username"], posts=data, taggedUsers=taggedUsers, searchedUser=searchedUser)

            message = "Searched user does not exist. Please try again."
            return render_template("home.html", message=message, username=session["username"])

    message = "Failed to search for user."
    return render_template("home.html", message=message, username=session["username"])

# Required Feature #3: Manage Follows
# Used to follow a user
@app.route("/follow", methods=["POST"])
@login_required
def follow():
    if request.form:
        requestData = request.form
        followee = requestData["followee"]
        follower = session["username"]
        acceptedFollow = 0

        try:
            # Query for when the user tries to follow some other user
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

# Required Feature #3: Manage Follows
# Used to unfollow a user
@app.route("/unfollow", methods=["POST"])
@login_required
def unfollow():
    if request.form:
        requestData = request.form
        unfollowee = requestData["unfollowee"]
        follower = session["username"]
        try:
            # Query used to remove the follow from the Follow table
            deleteQuery = "DELETE FROM Follow WHERE followeeUsername=%s AND followerUsername=%s"
            with connection.cursor() as cursor:
                if unfollowee != follower:
                    cursor.execute(deleteQuery, (unfollowee, follower))
                    message = "Unfollowed " + unfollowee        
                else:
                    message = "You can't unfollow yourself!"    
        except:
            message = "Failed to unfollow " + unfollowee            
        return render_template("followers.html", message=message, username=session["username"])
    else:
        return render_template("followers.html", username=session["username"])

# Required Feature #3: Manage Follows
# Helps display the followed and following users
@app.route("/followers", methods=["GET"])
@login_required
def displayFollowers():
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

# Required Feature #3: Manage Follows
# Helps manage the unfollow and follow status
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
                # If user chooses to accept a follow request, update the acceptedFollow
                updateQuery = "UPDATE Follow SET acceptedFollow=%s WHERE followeeUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(updateQuery, (1, followee))
            else:
                # If the user choose to decline the follow request, delete the follow
                deleteQ = "DELETE FROM Follow WHERE followerUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(deleteQ, (follower["followerUsername"]))
    return render_template("notifications.html", username=session["username"])

# Extra Feature #8: Like Photo
@app.route("/like", methods=["POST"])
@login_required
def like():
    if request.form:
        requestData = request.form
        liker = session["username"]
        photoID = requestData["likeID"]
        try:
            query = "INSERT INTO Liked (username, photoID, timestamp) VALUES (%s, %s, %s)"
            # exists = "SELECT * FROM Like WHERE username=%s"
            with connection.cursor() as cursor:
                cursor.execute(query, (liker, photoID, time.strftime('%Y-%m-%d %H:%M:%S')))
        #         cursor.execute(exists, (liker))
        # existData = cursor.fetchone()
        # if (existData):
            return redirect(url_for('images'))
        # else:
        except:
            message = "Unable to or already liked photo"
            return render_template("images.html", username=session["username"], message=message)
    return render_template("images.html", username=session["username"])

# Extra Feature #7: Add comments
@app.route("/comment", methods=["POST"])
@login_required
def comment():
    if request.form:
        requestData = request.form
        commenter = session["username"]
        comment = requestData["comment"]
        photoID = requestData["commentID"]
        insertQuery = "INSERT INTO Comment (username, photoID, commentText, timestamp) VALUES (%s, %s, %s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(insertQuery, (commenter, photoID,comment, time.strftime('%Y-%m-%d %H:%M:%S')))
        return render_template("images.html", username=session["username"])
    else:
        return render_template("images.html", username=session["username"])

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
