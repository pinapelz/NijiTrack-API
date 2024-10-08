import plotly.graph_objects as go
import pandas as pd
import warnings
from member_colors import member_color_map
import random

def plot_subscriber_count_over_time(server, table_name, gtitle="Subscriber Count Over Time for Phase Connect Members",
                                    markers="lines", exclude_channels=[]):
    warnings.filterwarnings('ignore') # Ignore pandas warning regarding pyodbc
    query = f"SELECT name, subscriber_count, timestamp, channel_id FROM {table_name} ORDER by timestamp DESC"
    df = pd.read_sql_query(query, server.get_connection())
    groups = df.groupby("name")
    fig = go.Figure()
    config = dict({'responsive': True, 'displaylogo': False, 'modeBarButtonsToAdd': ['pan2d', 'zoomIn2d', 'zoomOut2d']})
    
    for channel, group in groups:
        if len(exclude_channels) != 0 and group['channel_id'].iloc[0] in exclude_channels:
            continue
        color = None
        color = member_color_map.get(channel, '#' + ''.join(random.choices('0123456789ABCDEF', k=6)))
            
        fig.add_trace(go.Scattergl(
            x=group["timestamp"], y=group["subscriber_count"], name=channel, mode=markers,
            showlegend=True, line=dict(color=color)))
    
    fig.update_layout(
        title={'text': gtitle, 'x': 0.5, 'xanchor': 'center',
               'yanchor': 'top', 'font': {'family': 'Droid Sans', 'size': 30}},
        xaxis_title="Date",
        yaxis_title="Subscribers",
        legend=dict(font=dict(size=16), title=dict(text="Channels")),
        height=950,
    )
    return fig.to_html(config=config)
