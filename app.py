from collections import deque
from random import shuffle


from flask import Flask, jsonify, Response
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mydb.sqlite3'

db = SQLAlchemy(app)



class Game(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    category = db.Column(db.String(100), default="War")
    players = db.relationship('Player', lazy=True)


class Player(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class User(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    players = db.relationship('Player', lazy=True)
    interests = db.relationship('Interest', lazy=True)


class Interest(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


def assign_algorithm_score_for(user1, user2):
    # A user starts with 0 points
    # we add points for the similarities in interests
    algo_user = user1.__dict__.copy()
    algo_user['score'] = 0
    for interest in user1.interests:
        if interest.name in [i.name for i in user2.interests]:
            algo_user['score'] += 1
    return algo_user


@app.route('/user/<user>/next-opponent', methods=['GET'])
def get_next_opponent(user):
    # Code review changes to potentially make:
    """
        Lines SQL code below could provide a better solution for picking users we havent played before.

        -The original way could cause an issue with loading too many objects for memory
        - Creating multiple transactions to the database and processing them in python could be slower. Let the database handle more load
        -Add a limit to the number of results returned. You realistally dont need to find the perfect match just a good one. If you have too many users this could be extremely expensive
    """

    f'''     
            SELECT
                distinct potential_opponents.username
            FROM
                user as potential_opponents   
            LEFT JOIN
                player p1           
                    on potential_opponents.id = p1.user_id
            LEFT JOIN
                player p2           
                    on p2.game_id = p1.game_id
            LEFT JOIN
                user           
                    on user.id = p2.user_id   
            WHERE
                (
                    potential_opponents.username != '{user}'
                    AND         (
                        potential_opponents.username != user.username                           
                        AND             user.username != '{user}'
                        OR             user.username ISNULL                   
                    )               
                )
            LIMIT 500   
    '''
    # Find the current user
    current_user = User.query.filter_by(username=user).first()
    if not current_user:
        return Response(f"{user}: is not a valid username", status=404)

    # Find users who we previously played
    my_players = current_user.players # list of all player ids for brian
    games_played = Game.query.filter(Game.id.in_([player.game_id for player in my_players])).all()
    previously_played_with = Player.query.filter(Player.game_id.in_([game.id for game in games_played])).all()
    users_played_with = User.query.filter(User.id.in_([player.user_id for player in previously_played_with])).all()

    # Get list of people we haven't played with
    potential_users = User.query.filter(User.id.notin_([user.id for user in users_played_with])).all() # get other people
    if not potential_users:
        return Response("No valid opponents found", status=404)

    # assigning best user to one with best score
    best_user = None
    for user in potential_users:
        scored_user = assign_algorithm_score_for(user, current_user)
        if not best_user:
            best_user = scored_user
        else:
            best_user = max(best_user, scored_user, key=lambda i: i['score'])
    return jsonify(user_id=best_user['id'])


@app.route('/game-prediction')
def game_prediction():
    p1_deck = deque([1, 6, 3, 8, 9, 2, 4, 8, 2, 5, 2, 3, 3, 3, 9])
    p2_deck = deque([7, 2, 4, 3, 6, 2, 5, 1, 1, 4, 2, 3, 2, 2, 8])
    current_pot = []
    winning_player_id = None

    while p1_deck and p2_deck:
        #top of the deck is element 0
        p1_card = p1_deck.popleft()
        p2_card = p2_deck.popleft()
        current_pot.extend([p1_card,p2_card])
        if p1_card > p2_card: # player 1 wins and adds pot to deck
            shuffle(current_pot)
            p1_deck.extend(current_pot)
            current_pot = []
        elif p2_card > p1_card: # player 2 wins and adds pot to deck
            shuffle(current_pot)
            p2_deck.extend(current_pot)
            current_pot = []
        else: #war
            # Making up rule where if you run out of cards in tie you lose
            try: # using try except because faster than checking. Will only fail out once instead of checking list everytime.
                p1_face_down_card = p1_deck.popleft()
            except IndexError:
                winning_player_id = 2
                break
            try:
                p2_face_down_card = p2_deck.popleft()
            except IndexError:
                winning_player_id = 1
                break

            current_pot.extend([p1_face_down_card, p2_face_down_card])

    if p1_deck:
        winning_player_id = 'p1'
    else:
        winning_player_id = 'p2'
    return jsonify(winning_player_id=winning_player_id)


if __name__ == '__main__':
    app.run(debug=True)
