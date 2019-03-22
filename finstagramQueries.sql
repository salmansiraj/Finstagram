CREATE TABLE Person(
    username VARCHAR(20), 
    password CHAR(64), 
    fname VARCHAR(20),
    lname VARCHAR(20),
    PRIMARY KEY (username)
);

CREATE TABLE Photo(
    photoID int NOT NULL AUTO_INCREMENT,
    timestamp Timestamp,
    filePath VARCHAR(2048),
    PRIMARY KEY (photoID)
);