import numpy as np
from multiagent.core import World, Agent, Landmark
from multiagent.scenario import BaseScenario
from multiagent.scenarios.constants import D_LINE, O_LINE, Q_BACK

# D_LINE = 'd_line'
# O_LINE = 'o_line'
# Q_BACK = 'q_back'

class Scenario(BaseScenario):

    def make_world(self):
        world = World()
        # set any world properties first
        world.dim_c = 2
        num_offensive_linemen = 5 # Offensive linemen
        num_defensive_linemen = 7 # Defensive linemen
        num_quarterback = 1
        world.num_agents = num_offensive_linemen + num_defensive_linemen + num_quarterback
        world.borders = [[0,0], [53,120]]
        world.line_of_scrimmage = 60

        # Add defensive linemen
        d_line = [Agent() for i in range(num_defensive_linemen)]
        for i, d in enumerate(d_line):
            d.name = 'agent %d' % i
            d.collide = True # TODO: INVESTIGATE THIS VAL
            d.silent = True
            d.position = D_LINE
            d.size = 0.15 # TODO: INVESTIGATE THIS VAL
            d.in_bounds = True
            d.is_done = False
            d.color = np.array([0.25, 0.25, 0.25])
            world.agents.append(d)
            # world.policy_agents.append(d)

        # Add offensive linemen
        o_line = [Agent() for i in range(num_offensive_linemen)]
        for i, o in enumerate(o_line):
            o.name = 'agent %d' % (i + num_defensive_linemen)
            o.collide = True # TODO: INVESTIGATE THIS VAL
            o.silent = True
            o.position = O_LINE
            o.size = 0.15 # TODO: INVESTIGATE THIS VAL
            o.in_bounds = True
            o.is_done = False
            o.color = np.array([0.75, 0.25, 0.25])
            world.agents.append(o)
            # world.policy_agents.append(o)

        # Add quarterback
        q_back = Agent()
        q_back.name = 'agent %d' % (num_defensive_linemen + num_offensive_linemen)
        q_back.collide = True # TODO: INVESTIGATE THIS VAL
        q_back.silent = True
        q_back.position = Q_BACK
        q_back.size = 0.15
        q_back.in_bounds = True
        q_back.is_done = False
        q_back.color = np.array([0.25, 0.25, 0.75])
        world.agents.append(q_back)
        # world.policy_agents.append(q_back)

        # make initial conditions
        self.reset_world(world)
        return world

    def reset_world(self, world):
        # random properties for agents

        # random properties for landmarks
        
        # set random initial states
        for agent in world.agents:
            if (agent.position == D_LINE):
                y = world.line_of_scrimmage + 0.5
                x = np.random.uniform(21, 30) # TODO: As far as I can tell, this places them all between the hashes
                agent.state.p_pos = np.array([x, y])
                agent.accel = np.random.uniform(3.0, 4.0)
                agent.max_speed = np.random.uniform(1.0, 1.2)
            elif (agent.position == O_LINE):
                y = world.line_of_scrimmage - 0.5
                x = np.random.uniform(23, 28)
                agent.state.p_pos = np.array([x, y])
                agent.accel = np.random.uniform(3.0, 4.0)
                agent.max_speed = np.random.uniform(1.0, 1.2)
            elif (agent.position == Q_BACK):
                y = world.line_of_scrimmage - np.random.uniform(5, 10) # THESE ARE RANDOMLY CHOSEN BOUNDS
                x = 26
                agent.state.p_pos = np.array([x, y])
                agent.completion_percentage = np.random.uniform(0.5, 1)
                agent.accel = np.random.uniform(3.0, 4.0)
                agent.max_speed = np.random.uniform(1.0, 1.2)
            agent.is_done = False
            agent.in_bounds = True
            agent.state.p_vel = np.zeros(world.dim_p)
            agent.state.c = np.zeros(world.dim_c)

        world.first_down_line = np.random.uniform(2, 20)
        world.timeout = np.random.uniform(400, 600)
        world.time = 0


    # return all offensive players
    def offensive_agents(self, world):
        return [agent for agent in world.agents if ((agent.position == Q_BACK or agent.position == O_LINE) and agent.in_bounds and not agent.is_done)]

    # return all defensive players
    def defensive_agents(self, world):
        return [agent for agent in world.agents if (agent.position == D_LINE and agent.in_bounds and not agent.is_done)]

    def reward(self, agent, world):
        # Agents are rewarded based on minimum agent distance to each landmark
        if (agent.in_bounds):
            if (agent.position == D_LINE):
                return self.defensive_line_reward(agent, world)
            elif (agent.position == O_LINE):
                return self.offensive_line_reward(agent, world)
            elif (agent.position == Q_BACK):
                return self.offensive_line_reward(agent, world) # DO I NEED SOMETHING DIFFERENT?
        else:
            return -10 # If out of bounds, -10?

    # TODO REWARDS
    def offensive_line_reward(self, agent, world):
        # Rewarded based on how close any good agent is to the goal landmark, and how far the adversary is from it
        shaped_reward = True
        shaped_adv_reward = True

        # Calculate negative reward for adversary
        # adversary_agents = self.adversaries(world)
        # if shaped_adv_reward:  # distance-based adversary reward
        #     adv_rew = sum([np.sqrt(np.sum(np.square(a.state.p_pos - a.goal_a.state.p_pos))) for a in adversary_agents])
        # else:  # proximity-based adversary reward (binary)
        #     adv_rew = 0
        #     for a in adversary_agents:
        #         if np.sqrt(np.sum(np.square(a.state.p_pos - a.goal_a.state.p_pos))) < 2 * a.goal_a.size:
        #             adv_rew -= 5

        # Calculate positive reward for agents
        # offensive_agents = self.offensive_agents(world)
        # if shaped_reward:  # distance-based agent reward
        #     pos_rew = -min(
        #         [np.sqrt(np.sum(np.square(a.state.p_pos - a.goal_a.state.p_pos))) for a in good_agents])
        # else:  # proximity-based agent reward (binary)
        #     pos_rew = 0
        #     if min([np.sqrt(np.sum(np.square(a.state.p_pos - a.goal_a.state.p_pos))) for a in good_agents]) \
        #             < 2 * agent.goal_a.size:
        #         pos_rew += 5
        #     pos_rew -= min(
        #         [np.sqrt(np.sum(np.square(a.state.p_pos - a.goal_a.state.p_pos))) for a in good_agents])
        return 1 # +1 for each timestep the play continues

    def defensive_line_reward(self, agent, world):
        # Rewarded based on proximity to the goal landmark
        # shaped_reward = True
        # if shaped_reward:  # distance-based reward
        #     return -np.sum(np.square(agent.state.p_pos - agent.goal_a.state.p_pos))
        # else:  # proximity-based reward (binary)
        #     adv_rew = 0
        #     if np.sqrt(np.sum(np.square(agent.state.p_pos - agent.goal_a.state.p_pos))) < 2 * agent.goal_a.size:
        #         adv_rew += 5
        #     return adv_rew

        # TODO: REWARD DISTANCE FROM D LINE TO QUARTER BACK
        # q_back = [agent for agent in world.agents if agent.position == Q_BACK][0]
        # return -np.sqrt(np.sum(np.square(agent.state.p_pos - q_back.state.p_pos)))
        return -1 # -1 for each timestep the play continues


    def observation(self, agent, world):
        # Should observe 
        #   Position between itself and other players
        #   Position to boundaries/on field?

        other_pos = []
        for other in world.agents:
            if (other is agent):
                continue
            other_pos.append(other.state.p_pos - agent.state.p_pos)

        # if (len(other_pos)):
        return np.concatenate(other_pos)
        # return np.array([])
        # return other_pos


    def benchmark_data(self, agent, world):
        # returns data for benchmarking purposes
        if agent.position == D_LINE:
            # Benchmark the position from each D_LINE to Q_BACK
            q_back = world.get_agents().filter(lambda x: x.position == Q_BACK)
            return np.sum(np.square(q_back.state.p_pos - agent.state.p_pos))
        elif agent.position == Q_BACK:
            return world.line_of_scrimmage - agent.state.p_pos[1]
        elif agent.position == O_LINE:
            q_back = world.get_agents().filter(lambda x: x.position == Q_BACK)
            return np.sum(np.square(q_back.state.p_pos - agent.state.p_pos))
