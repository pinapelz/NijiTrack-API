import plotly.graph_objects as go
import pandas as pd
import warnings
from member_colors import member_color_map, member_groups
import random

def plot_subscriber_count_over_time(server, table_name, gtitle="Subscriber Count Over Time for Phase Connect Members",
                                    markers="lines", exclude_channels=[]):
    import plotly.graph_objects as go
    import pandas as pd
    import random
    import warnings
    from member_colors import member_color_map, member_groups

    warnings.filterwarnings('ignore')  # Ignore pandas warning regarding pyodbc
    query = f"SELECT name, subscriber_count, timestamp, channel_id FROM {table_name} ORDER by timestamp DESC"
    df = pd.read_sql_query(query, server.get_connection())
    if exclude_channels:
        df = df[~df['channel_id'].isin(exclude_channels)]
    df['group_name'] = df['name'].map(member_groups).fillna('Other')
    fig = go.Figure()
    config = dict({
        'responsive': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': ['pan2d', 'zoomIn2d', 'zoomOut2d']
    })
    group_names = sorted(df['group_name'].unique())

    for group_name in group_names:
        channels_in_group = sorted(df[df['group_name'] == group_name]['name'].unique())
        group_title_added = False  # Flag to add group title only once

        for channel in channels_in_group:
            group = df[(df['group_name'] == group_name) & (df['name'] == channel)]
            if len(exclude_channels) != 0 and group['channel_id'].iloc[0] in exclude_channels:
                continue

            color = member_color_map.get(channel, '#' + ''.join(random.choices('0123456789ABCDEF', k=6)))

            if not group_title_added:
                legendgrouptitle_text = group_name
                group_title_added = True
            else:
                legendgrouptitle_text = None

            fig.add_trace(go.Scattergl(
                x=group["timestamp"],
                y=group["subscriber_count"],
                name=channel,
                mode=markers,
                showlegend=True,
                line=dict(color=color),
                legendgroup=group_name,
                legendgrouptitle_text=legendgrouptitle_text,
                legendrank=group_names.index(group_name),
            ))

    fig.update_layout(
        title={
            'text': gtitle,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'family': 'Droid Sans', 'size': 30}
        },
        xaxis_title="Date",
        yaxis_title="Subscribers",
        legend=dict(
            font=dict(size=16),
            title=dict(text="Channels"),
            groupclick='toggleitem'
        ),
        height=950,
    )

    return fig.to_html(config=config)
