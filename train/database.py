import sqlite3
import threading


class DataBase:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.mutex = threading.Lock()
        print("open database successfully")

    def create_table(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS INFO "
                  "(NAME CHAR(100) NOT NULL,"
                  "TRACE CHAR(100) PRIMARY KEY NOT NULL,"
                  "LENGTH INT NOT NULL,"
                  "COVERAGE CHAR(1000));")
        print("Table created successfully")
        self.conn.commit()

    def store(self, names, trace):
        cmd = "INSERT OR IGNORE INTO INFO (NAME, TRACE, LENGTH) values (" \
              "\'" + names + "\',\'" + str(trace) + "\'," + str(len(trace)) + ")"
        try:
            if self.mutex.acquire(1):
                c = self.conn.cursor()
                c.execute(cmd)
                self.conn.commit()
                self.mutex.release()
        except Exception as e:
            print("store error %s" % e)

    def collect(self):
        ids = []
        cmd = "SELECT NAME, TRACE FROM INFO WHERE COVERAGE IS NULL"
        try:
            if self.mutex.acquire(1):
                c = self.conn.cursor()
                cursor = c.execute(cmd)
                self.mutex.release()
                for row in cursor:
                    ids.append(row)
                return ids
        except Exception as e:
            print("store error %s" % e)

    def setCover(self, trace, coverage):
        cmd = "UPDATE INFO SET COVERAGE =\'" + str(coverage) + "\' WHERE TRACE=\'" + str(trace) + "\'"
        try:
            if self.mutex.acquire(1):
                c = self.conn.cursor()
                c.execute(cmd)
                self.conn.commit()
                self.mutex.release()
        except Exception as e:
            print("setCover error %s" % e)

    def getCover(self, trace, name=None):
        if trace:
            cmd = "SELECT COVERAGE FROM INFO WHERE TRACE=\'" + str(trace) + "\'"
        elif name:
            cmd = "SELECT COVERAGE FROM INFO WHERE NAME=\'" + name + "\'"
        try:
            c = self.conn.cursor()
            cursor = c.execute(cmd)
            for row in cursor:
                return row[0]
        except Exception as e:
            print("getCover error %s" % e)

    def delete(self, trace):
        cmd = "DELETE FROM INFO WHERE TRACE=\'" + str(trace) + "\'"
        try:
            if self.mutex.acquire(1):
                c = self.conn.cursor()
                c.execute(cmd)
                self.conn.commit()
                self.mutex.release()
        except Exception as e:
            print("delete error %s" % e)

    def close(self):
        self.conn.close()