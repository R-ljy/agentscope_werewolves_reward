# -*- coding: utf-8 -*-
"""
Reward calculation module for the werewolf game.

You should import and call:
    reward_manager = RewardManager(players)
    reward_manager.record_night_action(...)
    reward_manager.record_day_vote(...)
    reward_manager.record_final_result(winning_side)
    reward_manager.compute_final_average()
"""

from collections import defaultdict


class RewardManager:
    def __init__(self, players):
        """
        players: Players instance from utils.py
        """
        self.players = players
        self.rewards = defaultdict(float)   # reward sum per agent
        self.counts = defaultdict(int)      # # of reward events per agent

    # ----------------------------------------------------------------------
    # Utility
    # ----------------------------------------------------------------------
    def _add(self, player_name: str, value: float):
        self.rewards[player_name] += value
        self.counts[player_name] += 1

    def _is_wolf(self, name):
        return self.players.name_to_role[name] == "werewolf"

    def _role(self, name):
        return self.players.name_to_role[name]

    # ----------------------------------------------------------------------
    # NIGHT REWARD LOGIC
    # ----------------------------------------------------------------------
    def record_night_action(
        self,
        killed_player: str | None,
        poisoned_player: str | None,
        shot_player: str | None,
        seer_checks: dict,
        witch_resurrect_info: dict,
    ):
        """
        killed_player: player killed by wolves
        poisoned_player: player poisoned by witch
        shot_player: player shot by hunter (night)
        seer_checks: {seer_name : target_name}
        witch_resurrect_info: {witch_name : resurrected_name_or_None}
        """

        # -------------------------
        # 1) Werewolves kill reward
        # -------------------------
        if killed_player:
            for wolf in self.players.role_to_names["werewolf"]:
                # kill role reward
                role = self._role(killed_player)
                if role == "seer":
                    self._add(wolf, 0.6)
                elif role == "witch":
                    self._add(wolf, 0.4)
                elif role == "hunter":
                    self._add(wolf, 0.2)
                elif role == "villager":
                    self._add(wolf, 0.1)
                elif role == "werewolf":
                    self._add(wolf, -1.0)  # kill teammate

        # -------------------------
        # 2) Witch resurrect reward
        # -------------------------
        for witch_name, resurrect_name in witch_resurrect_info.items():
            if resurrect_name:  # witch saved someone
                role = self._role(resurrect_name)
                if role != "werewolf":
                    self._add(witch_name, 0.4)  # saved good guy
                else:
                    self._add(witch_name, -0.2)  # saved wolf (bad)

        # -------------------------
        # 3) Witch poison reward
        # -------------------------
        if poisoned_player:
            # find the witch (only one)
            for witch in self.players.role_to_names["witch"]:
                role = self._role(poisoned_player)
                if role == "werewolf":
                    self._add(witch, 0.6)
                else:
                    self._add(witch, -0.8)

        # -------------------------
        # 4) Hunter shooting reward (night)
        # -------------------------
        if shot_player:
            for hunter in self.players.role_to_names["hunter"]:
                role = self._role(shot_player)
                if role == "werewolf":
                    self._add(hunter, 0.7)
                else:
                    self._add(hunter, -0.7)

        # -------------------------
        # 5) Seer checking reward
        # -------------------------
        for seer, target in seer_checks.items():
            role = self._role(target)
            if role == "werewolf":
                self._add(seer, 0.6)
            elif role == "villager":
                self._add(seer, 0.0)
            elif role == "seer":
                self._add(seer, 0.0)
            elif role == "witch":
                self._add(seer, 0.0)
            elif role == "hunter":
                self._add(seer, 0.0)

    # ----------------------------------------------------------------------
    # DAYTIME VOTING REWARD LOGIC
    # ----------------------------------------------------------------------
    def record_day_vote(self, votes_dict: dict, voted_player: str):
        """
        votes_dict: {voter_name : voted_name}
        voted_player: eliminated by vote
        """
        role_voted = self._role(voted_player)

        for voter, vote_target in votes_dict.items():
            role = self._role(voter)

            if self._is_wolf(voter):
                # Werewolf daytime behavior
                if role_voted == "seer":
                    self._add(voter, 0.7)
                elif role_voted == "witch":
                    self._add(voter, 0.5)
                elif role_voted == "villager":
                    self._add(voter, 0.2)
                elif role_voted == "hunter":
                    self._add(voter, 0.2)
                elif role_voted == "werewolf":
                    # protecting teammate
                    self._add(voter, 0.3)

            else:
                # Good guy daytime behavior
                if role_voted in ["villager", "seer", "witch", "hunter"]:
                    self._add(voter, -0.4)  # mis-elimination
                elif role_voted == "werewolf":
                    self._add(voter, 0.5)   # catching wolf

    # ----------------------------------------------------------------------
    # FINAL GAME RESULT REWARD
    # ----------------------------------------------------------------------
    def record_final_result(self, winning_side: str):
        """
        winning_side: "werewolf" or "village"
        """
        for name, role in self.players.name_to_role.items():
            if winning_side == "werewolf":
                if role == "werewolf":
                    self._add(name, +1)
                else:
                    self._add(name, -1)
            else:  # village win
                if role == "werewolf":
                    self._add(name, -1)
                else:
                    self._add(name, +1)

    # ----------------------------------------------------------------------
    # AVERAGE REWARD
    # ----------------------------------------------------------------------
    def compute_final_average(self):
        avg = {}
        for name in self.players.name_to_agent.keys():
            if self.counts[name] == 0:
                avg[name] = 0.0
            else:
                avg[name] = self.rewards[name] / self.counts[name]
        return avg

    # ----------------------------------------------------------------------
    # RESET (if needed)
    # ----------------------------------------------------------------------
    def reset(self):
        self.rewards = defaultdict(float)
        self.counts = defaultdict(int)

