from ctypes.wintypes import INT
import sqlite3
from csv import DictReader
from datetime import datetime
from enum import IntEnum

class Success(IntEnum):
    FALSE = 0
    TRUE = 1

INPUT_FILE = "asl_data.csv"
WORDS_TABLE = "words"
SESSIONS_TABLE = "sessions"
SCORES_TABLE = "scores"
DB_FILE_NAME = "flash_cards.db"

# Convenient SQL strings
SQL_INSERT_NEW_SESSION = "INSERT INTO sessions VALUES (\"{}\");"
SQL_MOST_RECENT_SESSION = "SELECT ROWID,MAX(date) FROM sessions;"
SQL_RANDOM_WORD = "SELECT _id, word FROM words ORDER BY RANDOM() LIMIT 1;"
SQL_INSERT_SCORE = "INSERT INTO scores VALUES({},{},{});"
SQL_SCORE_SESSION = "SELECT SUM(CORRECT) as correct FROM scores WHERE session_rowid={};"
SQL_SESSION_TOTAL = "SELECT COUNT(*) AS count FROM scores WHERE session_rowid={};"
SQL_INCORRECT_WORDS = "SELECT scores.word_id, words.word FROM scores, words WHERE words._id = scores.word_id AND scores.session_rowid={} AND scores.correct=0;"
SQL_INSERT_WORD = "INSERT INTO words (_id, level, word) VALUES({},{},\"{}\");"

class FlashCardsModel:

    def __init__(self, db_file: str ):
        self._db_file = db_file
        self._con = sqlite3.connect(DB_FILE_NAME)
        self._cur = self._con.cursor()
    
    def new_session(self) -> int:
        """Start a new session

        Returns:
            int: the rowID for the new session
        """

        # Insert a new record
        self._cur.execute( SQL_INSERT_NEW_SESSION.format(datetime.now().isoformat()) )
        self._cur.execute( SQL_MOST_RECENT_SESSION )
        row = self._cur.fetchone()

        # Commit the change
        self._con.commit()

        return row[0]
    
    def get_random_word(self) -> tuple:
        """Select a word at random from the database

        Returns:
            tuple: Tuple containing the (ID, word)
        """
        self._cur.execute(SQL_RANDOM_WORD)
        row = self._cur.fetchone()
        return (row[0], row[1])
    
    def score_word(self, session_id: int, word_id: int, success: bool):
        """Score a the given word in the given session with the given outcome

        Args:
            session_id (int): ROWID of the sessions
            word_id (int): ID of the word
            success (bool): If true, the user knew the word, false otherwise
        """
        # Insert a new record
        self._cur.execute(SQL_INSERT_SCORE.format(session_id, word_id, Success.TRUE if success else Success.FALSE ) )

        # Commit the change
        self._con.commit()
    
    def get_session_score( self, session_id: int ) -> float:
        """Get the score of the given session

        Args:
            session_id (int): The ID of the session of interest

        Returns:
            float: The percentage correct
        """
        self._cur.execute( SQL_SESSION_TOTAL.format( session_id ) )
        row = self._cur.fetchone()
        count = row[0]

        self._cur.execute( SQL_SCORE_SESSION.format( session_id ) )
        row = self._cur.fetchone()
        correct = row[0]

        return float(correct) / float(count)
    
    def get_incorrect_words( self, session_id: int ) -> list:
        """Get the words that we got wrong in this session

        Args:
            session_id (int): The Session we're talking about

        Returns:
            list: List of word tuples (id, word) that we got wrong
        """
        incorrect_words = []
        self._cur.execute( SQL_INCORRECT_WORDS.format(session_id) )
        rows = self._cur.fetchall()
        for row in rows:
            incorrect_words.append((row[0], row[1]))
        return incorrect_words



def erase_and_recreate_tables():
    """Erases and recreates all of the tables in the database
    """
    with sqlite3.connect(DB_FILE_NAME) as con:
        cur = con.cursor()

        # write some SQL strings
        drop_table_string = '''DROP TABLE IF EXISTS {};'''
        create_word_table_string = '''CREATE TABLE IF NOT EXISTS {} (
            _id INTEGER PRIMARY KEY,
            level INTEGER NOT NULL,
            word TEXT NOT NULL
        );'''.format( WORDS_TABLE )
        create_session_table_string = '''CREATE TABLE IF NOT EXISTS {} (
            date TEXT NOT NULL
            )'''.format(SESSIONS_TABLE)
        create_scores_table_string = '''CREATE TABLE IF NOT EXISTS {} (
            session_rowid INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            correct INTEGER NOT NULL
            )'''.format( SCORES_TABLE )
        
        # Create the tables
        cur.execute( drop_table_string.format(WORDS_TABLE) )
        cur.execute( create_word_table_string )
        cur.execute( drop_table_string.format(SESSIONS_TABLE) )
        cur.execute( create_session_table_string )
        cur.execute( drop_table_string.format(SCORES_TABLE) )
        cur.execute( create_scores_table_string )

        # grab the words form the input file
        reader = None
        with open( INPUT_FILE, "r", encoding="utf-8-sig" ) as in_file:
            reader = DictReader( in_file )

            # insert records
            for record in reader:
                cur.execute(SQL_INSERT_WORD.format(record['Number'], record['Level'], record['Word']))
        
        # Commit changes
        con.commit()

def update_word_list():
    with sqlite3.connect(DB_FILE_NAME) as con:
        cur = con.cursor()

        sql_find_word_by_id = "SELECT _id,level,word FROM words WHERE _id={};"
        sql_update_word = "UPDATE words SET word=\"{}\" WHERE _id={};"

        updated = 0
        added = 0
        checked = 0
        with open( INPUT_FILE, "r", encoding="utf-8-sig" ) as in_file:
            reader = DictReader( in_file )

            for record in reader:
                checked += 1
                # Check if we already have this record
                res = cur.execute( sql_find_word_by_id.format( record['Number'] ) )
                row = res.fetchone()
                if( row is not None ):
                    if( row[2] != record['Word'] ):
                        cur.execute( sql_update_word.format(record['Word'], record['Number']))
                        updated += 1
                    else:
                        # Do nothing, the records are identical
                        pass
                else:
                    cur.execute(SQL_INSERT_WORD.format(record['Number'], record['Level'], record['Word']))
                    added += 1

        
        # Done
        print( "Checked {} records, Updated {} and created {}".format(checked, updated, added))

        con.commit()

def test():
    from sys import stdin

    model = FlashCardsModel( DB_FILE_NAME )
    session_id = model.new_session()
    print( "Successfully created a new session with ID {}".format(session_id))

    # Get some random words
    for a in range( 5 ):
        word_id,word = model.get_random_word()
        print("Do you know how to sign (y/n): '{}'".format(word))
        user_input = stdin.readline()
        score = user_input.lower()[0] == "y"
        model.score_word( session_id, word_id, score )
    score = model.get_session_score( session_id )
    incorrect_words = model.get_incorrect_words( session_id )

    print( "This session you got {:0.1}% correct.".format( score * 100))
    print( "You should work on the following words: ")
    for word_id,word in incorrect_words:
        print( "\t{}. '{}'".format( word_id, word ) )


if __name__ == "__main__":
    test()