from enum import StrEnum

class EventIds(StrEnum):
    NONE = ""
    ON_JOIN = "on_join"
    ON_LEFT = "on_left"
    ON_KICK = "on_kick"
    ON_JOIN_NON_WHITELISTED = "on_join_non_whitelisted"
    
    ON_SERVER_START = "on_server_start"
    ON_SERVER_STOP = "on_server_stop"
    ON_SERVER_RESTART = "on_server_restart"
    
    ON_CONSOLE_CHAT = "on_console_chat"
    ON_SECURE_CHAT = "on_secure_chat"
    ON_SECURE_CHAT_OTHER = "on_secure_chat_other"
    ON_NON_SECURE_CHAT = "on_non_secure_chat"
    
    ON_ISSUE_COMMAND = "on_issue_command"
    ON_DEATH = "on_death"
    ON_RECALC_PLAYER_COUNT = "on_recalc_player_count"
    ON_ADVANCEMENT_COMPLETE = "on_advancement_complete"
    ON_GOAL_COMPLETE = "on_goal_complete"
    ON_CHALLENGE_COMPLETE = "on_challenge_complete"
    ON_ACHIEVEMENTS_COMPLETE_OLD = "on_achievements_complete_old"
    
    # integrations
    ON_CHAT_FROM_LUNACHAT = "on_chat_from_lunachat"
    
    # Other
    PLAYER_COUNT_NOTIFY = "player_count_notify"