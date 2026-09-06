"""Creative Lab workspace and session-local scenario controls."""
import json
from uuid import uuid4
import pandas as pd
import streamlit as st
from .lab import player_pool, projection


@st.cache_data(show_spinner=False)
def load_pool(rosters, history_path):
    return player_pool(rosters, history_path)


def render_lab(data, root, selected_team):
    st.title('Creative Lab')
    st.caption('Build an alternate NBA. Move players, invent prospects, tune rotations, and compare your scenario with the published league.')
    if 'lab_base' not in st.session_state:
        st.session_state.lab_base = load_pool(data['rosters'], root / 'data/raw/llimllib_nba_data/data/playerstats.parquet')
        st.session_state.lab_roster = st.session_state.lab_base.copy(deep=True)
        st.session_state.lab_forecast = data['next_forecast'].copy(deep=True)
        st.session_state.lab_snapshot = data['snapshot_root']
        st.session_state.lab_log = []
        st.session_state.lab_saved = {}
        st.session_state.lab_revision = 0
    state = st.session_state
    clubs = sorted(state.lab_forecast.team_abbr.unique())
    st.info('Experimental estimates: published wins plus the change in minutes-weighted player net rating × a sensitivity factor. This does not retrain the historical model or update market odds. Salary-cap and contract rules are not enforced.')
    st.caption('Your scenario stays in this browser session. Export it before closing or reloading. Its starting snapshot stays fixed until you reset.')
    if data['snapshot_root'] != state.lab_snapshot:
        st.warning('A newer live snapshot is available. Your experiment still uses its original baseline; reset to start from the new data.')
    team = st.selectbox('Lab team', clubs, index=clubs.index(selected_team) if selected_team in clubs else 0)
    sensitivity = st.slider('Win sensitivity per net-rating point', 0.0, 5.0, 2.7, .1, help='Illustrative conversion used by the roster diagnostic; not a calibrated causal effect.')
    def commit(frame, message):
        state.lab_roster = frame.reset_index(drop=True)
        state.lab_log.append(message)
        state.lab_revision += 1
        st.rerun()
    build, rotation, compare = st.tabs(['Roster builder', 'Rotation & development', 'Compare & export'])
    with build:
        available = state.lab_roster
        labels = {r.player_id:f'{r.player_name} · {r.team_abbr}' for r in available.itertuples()}
        with st.container(border=True):
            st.subheader('Trade, sign, or release')
            player = st.selectbox('Player', list(labels), format_func=labels.get)
            destination = st.selectbox('Destination', clubs + ['Free agents'], index=clubs.index(team))
            swap_options = ['None'] + available.loc[available.team_abbr.eq(destination) & available.player_id.ne(player),'player_id'].tolist()
            swap = st.selectbox('Return player (optional)', swap_options, format_func=lambda x: labels.get(x,x))
            st.caption('For a two-player trade, choose both players before applying. A free-agent destination releases the selected player.')
            if st.button('Apply move', type='primary'):
                frame = available.copy()
                origin = frame.loc[frame.player_id.eq(player),'team_abbr'].iloc[0]
                if origin == destination:
                    st.warning('Choose a different destination.')
                elif swap != 'None' and (swap == player or origin == 'Free agents'):
                    st.warning('A free-agent signing cannot send a return player. Choose None.')
                else:
                    frame.loc[frame.player_id.eq(player),'team_abbr'] = destination
                    if swap != 'None':
                        frame.loc[frame.player_id.eq(swap),'team_abbr'] = origin
                    commit(frame, f'{labels[player]} → {destination}' + (f'; return: {labels[swap]}' if swap != 'None' else ''))
        with st.form('lab_fantasy'):
            st.subheader('Create a fantasy signing')
            name = st.text_input('Player name', max_chars=80, placeholder='Your breakout prospect')
            minutes = st.slider('Expected minutes per game', 0, 48, 20)
            impact = st.slider('Assumed net rating', -20.0, 20.0, 0.0, .5)
            if st.form_submit_button('Add to lab team'):
                if not name.strip():
                    st.warning('Enter a player name.')
                elif len(available) >= len(state.lab_base) + 50:
                    st.warning('This scenario has reached its 50 custom-player limit.')
                else:
                    row = dict(player_id='fantasy-'+uuid4().hex, player_name=name.strip(), team_abbr=team, minutes=float(minutes), impact=impact, availability=100.0, evidence='User-created assumption')
                    commit(pd.concat([available,pd.DataFrame([row])],ignore_index=True), f'Created {name.strip()} on {team}')
        st.dataframe(state.lab_roster.loc[state.lab_roster.team_abbr.eq(team), ['player_name','minutes','impact','evidence']], hide_index=True, width='stretch')
    with rotation:
        st.subheader(f'{team} rotation')
        st.caption('Change minutes, availability, or net rating to explore injuries, development, and lineup roles. Missing minutes use neutral replacements; over 240 minutes are scaled proportionally.')
        current = state.lab_roster.loc[state.lab_roster.team_abbr.eq(team)].copy()
        if current.empty:
            st.info('Add players to this team in Roster builder.')
        else:
            edited = st.data_editor(current, hide_index=True, width='stretch', disabled=['player_id','player_name','team_abbr','evidence'], column_config={'player_id':None,'team_abbr':None,'minutes':st.column_config.NumberColumn('Minutes / game',min_value=0,max_value=48),'impact':st.column_config.NumberColumn('Net rating',min_value=-20,max_value=20),'availability':st.column_config.NumberColumn('Availability %',min_value=0,max_value=100)}, key=f'rotation_{team}_{state.lab_revision}')
            if st.button('Apply rotation'):
                frame = state.lab_roster.copy()
                frame.loc[current.index,['minutes','impact','availability']] = edited[['minutes','impact','availability']].to_numpy()
                try:
                    projection(state.lab_base,frame,state.lab_forecast,sensitivity)
                    commit(frame,f'Updated {team} rotation and player assumptions')
                except ValueError as error:
                    st.error(str(error))
    result = projection(state.lab_base,state.lab_roster,state.lab_forecast,sensitivity)
    with compare:
        title = st.text_input('Scenario name', value='My alternate NBA', max_chars=80)
        if st.button('Save comparison in session'):
            if len(state.lab_saved) >= 10 and title not in state.lab_saved:
                st.warning('Keep up to 10 comparisons per session.')
            else:
                state.lab_saved[title] = result.copy()
        for name, saved in state.lab_saved.items():
            with st.expander(name):
                st.dataframe(saved.round(2),hide_index=True,width='stretch')
        exported = dict(version=1, name=title, baseline_snapshot=state.lab_snapshot, sensitivity=sensitivity, roster=state.lab_roster.to_dict('records'), moves=state.lab_log, results=result.to_dict('records'))
        st.download_button('Export scenario JSON',json.dumps(exported,indent=2),file_name='nba-lab-scenario.json',mime='application/json')
        st.download_button('Export projections CSV',result.to_csv(index=False),file_name='nba-lab-projections.csv',mime='text/csv')
        if state.lab_log:
            st.write('Scenario history')
            for event in state.lab_log:
                st.text(event)
        confirm = st.checkbox('Discard this experiment and start from the latest snapshot')
        if st.button('Reset lab', disabled=not confirm):
            for key in list(state):
                if key.startswith('lab_') or key.startswith('rotation_'):
                    del state[key]
            st.rerun()
    st.subheader('Scenario results')
    row = result[result.team_abbr.eq(team)].iloc[0]
    a,b,c = st.columns(3)
    a.metric('Published wins',f'{row.holistic_predicted_wins:.1f}')
    b.metric('Scenario wins',f'{row.scenario_wins:.1f}',f'{row.change:+.1f}')
    c.metric('Scenario league rank',f'#{result.index[result.team_abbr.eq(team)][0]+1}')
    st.dataframe(result.rename(columns={'team_abbr':'Team','holistic_predicted_wins':'Published wins','scenario_wins':'Scenario wins','change':'Win change','rotation_delta':'Rotation rating change'}).round(2),hide_index=True,width='stretch')
