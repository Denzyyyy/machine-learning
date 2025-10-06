import sqlite3
import json
from datetime import datetime

timeframe = '2015-04'
sql_transaction = []


connection = sqlite3.connect('{}.db'.format(timeframe))
c = connection.cursor()
    
def create_table():
    
    c.execute("""CREATE TABLE IF NOT EXISTS parent_reply
              (parent_id TEXT PRIMARY KEY, comment_id TEXT UNIQUE, parent TEXT,comment TEXT
              , subreddit TEXT , unix INT, score INT)""")
    print("table created")
    
connection.commit()
    
    
  ## replace new line characters and double quotes in the data to avoid issues when inserting into the database.
def format_data(data):
    data = data.replace('\n', ' newlinechar ').replace('\r', ' newlinechar ').replace('"', "'")
    return data
    
    
def find_parent(parent_id):
    try:
        c.execute("SELECT comment FROM parent_reply WHERE comment_id = ? LIMIT 1", (parent_id,))
        row = c.fetchone()
        return row[0] if row else None
    except Exception as e:
        return None

    
    
def acceptable(data):
    if len(data.split(' ')) > 50 or len(data) < 1:
        return False
    elif len(data) > 1000:
        return False
    elif data == '[deleted]' or data == '[removed]':
        return False
    else:
        return True
    
       
def find_existing_score(parent_id):
    try:
        c.execute("SELECT CAST(score AS INTEGER) FROM parent_reply WHERE parent_id = ? LIMIT 1", (parent_id,))
        row = c.fetchone()
        return row[0] if row is not None else None
    except Exception:
        return None

    
def transaction_bldr(sql):
    global sql_transaction
    sql_transaction.append(sql)
    if len(sql_transaction) > 1000:
        c.execute('BEGIN TRANSACTION')
        for s in sql_transaction:
            try:
                if type(s) == str:
                    c.execute(s)
                else:
                    c.execute(s[0], s[1])
            except Exception as e:
                print('s-transaction', str(e))
        connection.commit()
        sql_transaction = []
    
def sql_insert_replace_comment(parent_id, comment_id, parent, comment, subreddit, created_utc, score):
    try:
        sql = """UPDATE parent_reply
                 SET comment_id = ?, parent = ?, comment = ?, subreddit = ?, unix = ?, score = ?
                 WHERE parent_id = ?;"""
        transaction_bldr((sql, (comment_id, parent, comment, subreddit, created_utc, score, parent_id)))
    except Exception as e:
        print('s-UPDATE insertion', str(e))

        
def sql_insert_has_parent(comment_id, parent_id, parent, comment, subreddit, created_utc, score):
    sql = """
    INSERT INTO parent_reply (parent_id, comment_id, parent, comment, subreddit, unix, score)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(parent_id) DO UPDATE SET
      comment_id = CASE WHEN excluded.score > parent_reply.score THEN excluded.comment_id ELSE parent_reply.comment_id END,
      parent     = COALESCE(parent_reply.parent, excluded.parent),
      comment    = CASE WHEN excluded.score > parent_reply.score THEN excluded.comment ELSE parent_reply.comment END,
      subreddit  = CASE WHEN excluded.score > parent_reply.score THEN excluded.subreddit ELSE parent_reply.subreddit END,
      unix       = CASE WHEN excluded.score > parent_reply.score THEN excluded.unix ELSE parent_reply.unix END,
      score      = MAX(parent_reply.score, excluded.score);
    """
    transaction_bldr((sql, (parent_id, comment_id, parent, comment, subreddit, created_utc, score)))

def sql_insert_no_parent(comment_id, parent_id, comment, subreddit, created_utc, score):
    sql = """
    INSERT INTO parent_reply (parent_id, comment_id, parent, comment, subreddit, unix, score)
    VALUES (?, ?, NULL, ?, ?, ?, ?)
    ON CONFLICT(parent_id) DO UPDATE SET
      comment_id = CASE WHEN excluded.score > parent_reply.score THEN excluded.comment_id ELSE parent_reply.comment_id END,
      parent     = COALESCE(parent_reply.parent, excluded.parent),
      comment    = CASE WHEN excluded.score > parent_reply.score THEN excluded.comment ELSE parent_reply.comment END,
      subreddit  = CASE WHEN excluded.score > parent_reply.score THEN excluded.subreddit ELSE parent_reply.subreddit END,
      unix       = CASE WHEN excluded.score > parent_reply.score THEN excluded.unix ELSE parent_reply.unix END,
      score      = MAX(parent_reply.score, excluded.score);
    """
    transaction_bldr((sql, (parent_id, comment_id, comment, subreddit, created_utc, score)))
    

if __name__ == '__main__':
    create_table()
    row_counter = 0
    paired_rows = 0
    
    with open(r"C:\Users\izahc\Downloads\reddit_data\{}\RC_{}".format(timeframe.split('-')[0], timeframe), buffering=1000) as f:
        for row in f:
            row_counter += 1
            row = json.loads(row)
            
            parent_id   = row['parent_id']
            body        = format_data(row['body'])
            created_utc = int(row['created_utc'])
            score       = int(row['score'])
            comment_id  = row['name']
            subreddit   = row['subreddit']
            
            parent_data = find_parent(parent_id)
            
            if score >= 2 and acceptable(body):
                if parent_data:
                    sql_insert_has_parent(comment_id, parent_id, parent_data, body, subreddit, created_utc, score)
                    paired_rows += 1
                else:
                    sql_insert_no_parent(comment_id, parent_id, body, subreddit, created_utc, score)


            if row_counter % 100000 == 0:
                print('Total Rows Read: {}, Paired Rows: {}, Time: {}'.format(row_counter, paired_rows, str(datetime.now())))
                
        
            