from ..contacts_data_processing import import_contact_info as ici
import importlib
from datetime import datetime
import pandas as pd


def main(data): 
    contacts = ici.main()
    contacts['phone_number'] = contacts['phone_number'].apply(lambda x: '+1' + x if isinstance(x, str) else x)

    # Get dope tracks members by handle_id
    dope_tracks_members = data['chat_handle_join'][data['chat_handle_join']['chat_id'].isin([16, 286])]['handle_id'].unique()
    dope_tracks_members_df = pd.DataFrame(dope_tracks_members, columns=['handle_id'])
    me = pd.DataFrame({'handle_id': [1]})
    dope_tracks_members_df = pd.concat([dope_tracks_members_df, me], ignore_index=True)

    # Merge handle data
    dope_tracks_members_df = pd.merge(
        dope_tracks_members_df,
        data['handles'][['handle_id', 'contact_info']],
        on='handle_id',
        how='left'
    ).sort_values('contact_info')

    # Get activity by handle_id
    dopetracks_activity = data['messages'][
        data['messages']['chat_id'].isin([16, 286]) &
        (data['messages']['date'] >= datetime(2024, 1, 1)) & 
        (data['messages']['date'] < datetime(2025, 1, 1))
    ].groupby('sender_handle_id').agg(
        messages_sent=('sender_handle_id', 'size'),
        non_reaction_messages=('reaction_type', lambda x: x.eq('no-reaction').sum()),
        loves_sent=('reaction_type', lambda x: x.eq('Loved').sum()),
        likes_sent=('reaction_type', lambda x: x.eq('Liked').sum()),
        hahas_sent=('reaction_type', lambda x: x.eq('Laughed').sum()),
        dislikes_sent=('reaction_type', lambda x: x.eq('Disliked').sum()),
        questions_sent=('reaction_type', lambda x: x.eq('Questioned').sum()),
        emphasized_sent=('reaction_type', lambda x: x.eq('Emphasized').sum()),
        links_sent=('spotify_song_links', lambda x: sum(1 for links in x if len(links) > 0)),
        first_message_date=('date', 'min'),
        last_message_date=('date', 'max')
    ).fillna({'messages_sent': 0, 'non_reaction_messages': 0, 'loves_sent': 0, 'links_sent': 0}).reset_index()

    # Merge activity with handles
    dopetracks_handle_activity = pd.merge(
        dope_tracks_members_df,
        dopetracks_activity,
        left_on="handle_id",
        right_on="sender_handle_id",
        how="left"
    ).fillna({'messages_sent': 0, 'non_reaction_messages': 0, 'loves_sent': 0, 'links_sent': 0}).sort_values('messages_sent', ascending=False)

    dopetracks_handle_activity_with_names = pd.merge(
        dopetracks_handle_activity,
        contacts,
        left_on="contact_info",
        right_on="phone_number",
        how="left"
    ).fillna({'first_name': "unknown", 'last_name': "unknown"})


    # Merge with contacts and group by name
    user_stats = dopetracks_handle_activity_with_names.groupby(["contact_info", "first_name", "last_name"]).agg(
        messages_sent=('messages_sent', 'sum'),
        non_reaction_messages=('non_reaction_messages', 'sum'),
        loves_sent=('loves_sent', 'sum'),
        likes_sent=('likes_sent', 'sum'),
        hahas_sent=('hahas_sent', 'sum'),
        dislikes_sent=('dislikes_sent', 'sum'),
        questions_sent=('questions_sent', 'sum'),
        emphasized_sent=('emphasized_sent', 'sum'),
        links_sent=('links_sent', 'sum'),
        first_message_date=('first_message_date', 'min'),
        last_message_date=('last_message_date', 'max'),
        handles = ('handle_id', 'unique')
    ).fillna({'messages_sent': 0,'non_reaction_messages': 0, 'loves_sent': 0, 'links_sent': 0}).sort_values('messages_sent', ascending=False).reset_index()

    return {
        "user_stats": user_stats
    }

if __name__ == "__main__":
    main()