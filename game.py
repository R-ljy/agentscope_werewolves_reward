# -*- coding: utf-8 -*-
# pylint: disable=too-many-branches, too-many-statements, no-name-in-module
"""A werewolf game implemented by agentscope."""
import numpy as np

from utils import (
    majority_vote,
    names_to_str,
    EchoAgent,
    MAX_GAME_ROUND,
    MAX_DISCUSSION_ROUND,
    Players,
)
from structured_model import (
    DiscussionModel,
    get_vote_model,
    get_poison_model,
    WitchResurrectModel,
    get_seer_model,
    get_hunter_model,
)
from prompt import EnglishPrompts as Prompts
from agentscope.agent import ReActAgent
from agentscope.pipeline import MsgHub, sequential_pipeline, fanout_pipeline

# <<< ADDED FOR REWARD >>>
from reward import RewardManager
# <<< END >>>

moderator = EchoAgent()


async def hunter_stage(
    hunter_agent: ReActAgent,
    players: Players,
) -> str | None:
    msg_hunter = await hunter_agent(
        await moderator(Prompts.to_hunter.format(name=hunter_agent.name)),
        structured_model=get_hunter_model(players.current_alive),
    )
    if msg_hunter.metadata.get("shoot"):
        return msg_hunter.metadata.get("name", None)
    return None


async def werewolves_game(agents: list[ReActAgent]) -> None:
    assert len(agents) == 9, "The werewolf game needs exactly 9 players."

    players = Players()

    # <<< ADDED FOR REWARD >>>
    reward_manager = RewardManager(players)
    # <<< END >>>

    healing, poison = True, True
    first_day = True

    async with MsgHub(participants=agents) as greeting_hub:
        await greeting_hub.broadcast(
            await moderator(
                Prompts.to_all_new_game.format(names_to_str(agents)),
            ),
        )

    roles = ["werewolf"] * 3 + ["villager"] * 3 + ["seer", "witch", "hunter"]
    np.random.shuffle(agents)
    np.random.shuffle(roles)

    for agent, role in zip(agents, roles):
        await agent.observe(
            await moderator(
                f"[{agent.name} ONLY] {agent.name}, your role is {role}.",
            ),
        )
        players.add_player(agent, role)

    players.print_roles()

    # GAME LOOP
    for _ in range(MAX_GAME_ROUND):

        async with MsgHub(
            participants=players.current_alive,
            enable_auto_broadcast=False,
            name="alive_players",
        ) as alive_players_hub:

            # ---- NIGHT BEGIN ----
            await alive_players_hub.broadcast(
                await moderator(Prompts.to_all_night),
            )
            killed_player, poisoned_player, shot_player = None, None, None

            # WOLF DISCUSSION --------------------
            async with MsgHub(
                players.werewolves,
                enable_auto_broadcast=True,
                announcement=await moderator(
                    Prompts.to_wolves_discussion.format(
                        names_to_str(players.werewolves),
                        names_to_str(players.current_alive),
                    ),
                ),
                name="werewolves",
            ) as werewolves_hub:

                n_werewolves = len(players.werewolves)
                for i in range(1, MAX_DISCUSSION_ROUND * n_werewolves + 1):
                    res = await players.werewolves[i % n_werewolves](
                        structured_model=DiscussionModel,
                    )
                    if i % n_werewolves == 0 and res.metadata.get("reach_agreement"):
                        break

                werewolves_hub.set_auto_broadcast(False)
                msgs_vote = await fanout_pipeline(
                    players.werewolves,
                    msg=await moderator(content=Prompts.to_wolves_vote),
                    structured_model=get_vote_model(players.current_alive),
                    enable_gather=False,
                )

                killed_player, votes = majority_vote(
                    [_.metadata.get("vote") for _ in msgs_vote],
                )

                await werewolves_hub.broadcast(
                    [
                        *msgs_vote,
                        await moderator(
                            Prompts.to_wolves_res.format(votes, killed_player),
                        ),
                    ],
                )

            # WITCH ----------------------------------
            await alive_players_hub.broadcast(
                await moderator(Prompts.to_all_witch_turn),
            )
            msg_witch_poison = None
            resurrected_player = None

            for agent in players.witch:
                msg_witch_resurrect = None
                if healing and killed_player != agent.name:
                    msg_witch_resurrect = await agent(
                        await moderator(
                            Prompts.to_witch_resurrect.format(
                                witch_name=agent.name,
                                dead_name=killed_player,
                            ),
                        ),
                        structured_model=WitchResurrectModel,
                    )
                    if msg_witch_resurrect.metadata.get("resurrect"):
                        resurrected_player = killed_player
                        killed_player = None
                        healing = False

                if poison and not (msg_witch_resurrect and msg_witch_resurrect.metadata["resurrect"]):
                    msg_witch_poison = await agent(
                        await moderator(
                            Prompts.to_witch_poison.format(
                                witch_name=agent.name,
                            ),
                        ),
                        structured_model=get_poison_model(players.current_alive),
                    )
                    if msg_witch_poison.metadata.get("poison"):
                        poisoned_player = msg_witch_poison.metadata.get("name")
                        poison = False

            # SEER ------------------------------------
            await alive_players_hub.broadcast(await moderator(Prompts.to_all_seer_turn))

            seer_checks = {}
            for agent in players.seer:
                msg_seer = await agent(
                    await moderator(
                        Prompts.to_seer.format(
                            agent.name,
                            names_to_str(players.current_alive),
                        ),
                    ),
                    structured_model=get_seer_model(players.current_alive),
                )
                if msg_seer.metadata.get("name"):
                    target = msg_seer.metadata["name"]
                    seer_checks[agent.name] = target
                    await agent.observe(
                        await moderator(
                            Prompts.to_seer_result.format(
                                agent_name=target,
                                role=players.name_to_role[target],
                            ),
                        ),
                    )

            # HUNTER ----------------------------------
            for agent in players.hunter:
                if killed_player == agent.name and poisoned_player != agent.name:
                    shot_player = await hunter_stage(agent, players)

            # UPDATE NIGHT DEATHS
            dead_tonight = [killed_player, poisoned_player, shot_player]
            players.update_players(dead_tonight)

            # <<< ADDED FOR REWARD: NIGHT REWARD >>>
            reward_manager.record_night_action(
                killed_player=killed_player,
                poisoned_player=poisoned_player,
                shot_player=shot_player,
                seer_checks=seer_checks,
                witch_resurrect_info={witch: resurrected_player for witch in players.role_to_names["witch"]},
            )
            # <<< END >>>

            # ---- DAY PHASE ----
            if len([_ for _ in dead_tonight if _]) > 0:
                await alive_players_hub.broadcast(
                    await moderator(
                        Prompts.to_all_day.format(
                            names_to_str([_ for _ in dead_tonight if _]),
                        ),
                    ),
                )

                if killed_player and first_day:
                    msg_moderator = await moderator(
                        Prompts.to_dead_player.format(killed_player),
                    )
                    await alive_players_hub.broadcast(msg_moderator)
                    last_msg = await players.name_to_agent[killed_player]()
                    await alive_players_hub.broadcast(last_msg)
            else:
                await alive_players_hub.broadcast(await moderator(Prompts.to_all_peace))

            # WIN CHECK
            res = players.check_winning()
            if res:
                await moderator(res)
                break

            # DISCUSSION
            await alive_players_hub.broadcast(
                await moderator(
                    Prompts.to_all_discuss.format(
                        names=names_to_str(players.current_alive),
                    ),
                ),
            )
            alive_players_hub.set_auto_broadcast(True)
            await sequential_pipeline(players.current_alive)
            alive_players_hub.set_auto_broadcast(False)

            # VOTING -------------------------------
            msgs_vote = await fanout_pipeline(
                players.current_alive,
                await moderator(
                    Prompts.to_all_vote.format(
                        names_to_str(players.current_alive),
                    ),
                ),
                structured_model=get_vote_model(players.current_alive),
                enable_gather=False,
            )

            voted_player, votes = majority_vote(
                [_.metadata.get("vote") for _ in msgs_vote],
            )

            voting_msgs = [
                *msgs_vote,
                await moderator(
                    Prompts.to_all_res.format(votes, voted_player),
                ),
            ]

            if voted_player:
                prompt_msg = await moderator(
                    Prompts.to_dead_player.format(voted_player),
                )
                last_msg = await players.name_to_agent[voted_player](prompt_msg)
                voting_msgs.extend([prompt_msg, last_msg])

            await alive_players_hub.broadcast(voting_msgs)

            # HUNTER (DAY)
            shot_player_day = None
            for agent in players.hunter:
                if voted_player == agent.name:
                    shot_player_day = await hunter_stage(agent, players)
                    if shot_player_day:
                        await alive_players_hub.broadcast(
                            await moderator(
                                Prompts.to_all_hunter_shoot.format(shot_player_day),
                            ),
                        )

            dead_today = [voted_player, shot_player_day]
            players.update_players(dead_today)

            # <<< ADDED FOR REWARD: DAY VOTE REWARD >>>
            reward_manager.record_day_vote(
                {m.agent_name: m.metadata["vote"] for m in msgs_vote},
                voted_player=voted_player,
            )
            # <<< END >>>

            # WIN CHECK AGAIN --------------------------
            res = players.check_winning()
            if res:
                async with MsgHub(players.all_players) as all_players_hub:
                    res_msg = await moderator(res)
                    await all_players_hub.broadcast(res_msg)
                break

        first_day = False

    # GAME OVER ---------------------------------------------
    await fanout_pipeline(
        agents=agents,
        msg=await moderator(Prompts.to_all_reflect),
    )

    # <<< ADDED FOR REWARD: FINAL RESULT >>>
    final_res = players.check_winning()
    winning_side = "werewolf" if "wolf" in final_res.lower() else "village"
    reward_manager.record_final_result(winning_side)

    print("=== Final Average Reward ===")
    print(reward_manager.compute_final_average())
    # <<< END >>>
