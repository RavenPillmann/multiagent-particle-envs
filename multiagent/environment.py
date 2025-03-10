import gym
from gym import spaces
from gym.envs.registration import EnvSpec
import numpy as np
from multiagent.multi_discrete import MultiDiscrete
from multiagent.scenarios.constants import D_LINE, O_LINE, Q_BACK

NOT_DONE = 0
Q_BACK_FIRST_DOWN_LINE = 1
AGENT_OUT_OF_BOUNDS = 2
D_LINE_REACHED_Q_BACK = 3
Q_BACK_NOT_IN_BOUNDS = 4
Q_BACK_THREW_BALL = 5

# environment for all agents in the multiagent world
# currently code assumes that no agents will be created/destroyed at runtime!
class MultiAgentEnv(gym.Env):
    metadata = {
        'render.modes' : ['human', 'rgb_array']
    }

    def __init__(self, world, reset_callback=None, reward_callback=None,
                 observation_callback=None, info_callback=None,
                 done_callback=None, shared_viewer=True):

        self.world = world
        self.agents = self.world.policy_agents
        # set required vectorized gym env property
        self.n = len(world.policy_agents)
        # scenario callbacks
        self.reset_callback = reset_callback
        self.reward_callback = reward_callback
        self.observation_callback = observation_callback
        self.info_callback = info_callback
        # self.done_callback = _done_callback
        # environment parameters
        self.discrete_action_space = True
        # if true, action is a number 0...N, otherwise action is a one-hot N-dimensional vector
        self.discrete_action_input = False
        # if true, even the action is continuous, action will be performed discretely
        self.force_discrete_action = world.discrete_action if hasattr(world, 'discrete_action') else False
        # if true, every agent has the same reward
        self.shared_reward = world.collaborative if hasattr(world, 'collaborative') else False
        self.time = 0

        # configure spaces
        self.action_space = []
        self.observation_space = []
        for agent in self.get_agents():
            total_action_space = []
            # physical action space
            if self.discrete_action_space:
                u_action_space = spaces.Discrete(world.dim_p * 2 + 1)
            else:
                u_action_space = spaces.Box(low=-agent.u_range, high=+agent.u_range, shape=(world.dim_p,), dtype=np.float32)
            if agent.movable:
                total_action_space.append(u_action_space)
            # communication action space
            if self.discrete_action_space:
                c_action_space = spaces.Discrete(world.dim_c)
            else:
                c_action_space = spaces.Box(low=0.0, high=1.0, shape=(world.dim_c,), dtype=np.float32)
            if not agent.silent:
                total_action_space.append(c_action_space)
            # total action space
            if len(total_action_space) > 1:
                # all action spaces are discrete, so simplify to MultiDiscrete action space
                if all([isinstance(act_space, spaces.Discrete) for act_space in total_action_space]):
                    act_space = MultiDiscrete([[0, act_space.n - 1] for act_space in total_action_space])
                else:
                    act_space = spaces.Tuple(total_action_space)
                self.action_space.append(act_space)
            else:
                self.action_space.append(total_action_space[0])
            # observation space
            obs_dim = len(observation_callback(agent, self.world))
            self.observation_space.append(spaces.Box(low=-np.inf, high=+np.inf, shape=(obs_dim,), dtype=np.float32))
            agent.action.c = np.zeros(self.world.dim_c)

        # rendering
        self.shared_viewer = shared_viewer
        if self.shared_viewer:
            self.viewer = None
        else:
            self.viewers = [None] * self.n
        self._reset_render()

    def get_agents(self):
        return [agent if not agent.is_done else None for agent in self.agents]

    def step(self, action_n):
        obs_n = []
        reward_n = []
        done_n = []
        info_n = {'n': []}
        self.agents = self.world.policy_agents
        # print(self.agents)
        # set action for each agent
        for i, agent in enumerate(self.agents):
            self._set_action(action_n[i], agent, self.action_space[i])
        # advance world state
        self.world.step()
        # record observation for each agent
        # print("New step")

        chance_of_completion = np.random.uniform(0.0, 1.0)
        made_throw = chance_of_completion < list(filter(lambda player: player.position == 'q_back', self.world.agents))[0].completion_percentage

        for agent in self.agents:
            obs_n.append(self._get_obs(agent))
            reward = self._get_reward(agent)
            is_done = self.done_callback(agent, self.world)
            done_n.append(is_done)
            # TODO: 
            # If done, I need to somehow indicate that so that no more actions are taken...
            # if (agent.position == 'q_back'):
                # print(agent.state.p_pos, self.world.line_of_scrimmage, agent.state.p_pos[1], self.world.line_of_scrimmage - agent.state.p_pos[1])
            if is_done != NOT_DONE:
                agent.is_done = True

                # print("agent position", agent.position)
                # print(agent.state.p_pos)

                additional_reward = self.get_final_reward(is_done, agent, made_throw)

                # print("additional_reward", additional_reward)
                reward = reward + additional_reward

            reward_n.append(reward)
            info_n['n'].append(self._get_info(agent))

        # all agents get total reward in cooperative case
        reward = np.sum(reward_n)
        if self.shared_reward:
            reward_n = [reward] * self.n

        return obs_n, reward_n, done_n, info_n



    def get_final_reward(self, is_done, agent, made_throw):
        # print(is_done, Q_BACK_NOT_IN_BOUNDS)

        if (is_done == Q_BACK_FIRST_DOWN_LINE):
            if (agent.position == O_LINE) or (agent.position == Q_BACK):
                return 120
            else:
                return -120
        elif (is_done == AGENT_OUT_OF_BOUNDS):
            return -80
        elif (is_done == D_LINE_REACHED_Q_BACK):
            if (agent.position == O_LINE) or (agent.position == Q_BACK):
                return -120 # TODO 
            else:
                return 120
        elif is_done == Q_BACK_NOT_IN_BOUNDS:
            if (agent.position == O_LINE) or (agent.position == Q_BACK):
                return -80
            else:
                return 80
        elif is_done == Q_BACK_THREW_BALL:
            if (agent.position == O_LINE) or (agent.position == Q_BACK):
                return 80 if made_throw else -80
            else:
                return -80 if made_throw else 80


    def reset(self):
        # reset world
        self.reset_callback(self.world)
        # reset renderer
        self._reset_render()
        # record observations for each agent
        obs_n = []
        self.agents = self.world.policy_agents
        for agent in self.get_agents():
            obs = None
            if agent:
                obs = self._get_obs(agent)
            obs_n.append(obs)
        return obs_n

    # get info used for benchmarking
    def _get_info(self, agent):
        if self.info_callback is None:
            return {}
        return self.info_callback(agent, self.world)

    # get observation for a particular agent
    def _get_obs(self, agent):
        if self.observation_callback is None:
            return np.zeros(0)
        return self.observation_callback(agent, self.world)

    # get dones for a particular agent
    # unused right now -- agents are allowed to go beyond the viewing screen
    # def _get_done(self, agent):
    #     if self.done_callback is None:
    #         return False
    #     return self.done_callback(agent, self.world)

    def done_callback(self, agent, world):    
        # Use world.timeout, and see what's wrong
        if world.time > world.timeout:
            return Q_BACK_THREW_BALL

        # Agent is done if it is out of bounds
        if (not agent.in_bounds):
            return AGENT_OUT_OF_BOUNDS

        q_back = list(filter(lambda player: player.position == 'q_back', world.agents))[0]
        d_line = list(filter(lambda player: player.position == 'd_line', world.agents))
        line_of_scrimmage = world.line_of_scrimmage
        q_pos = q_back.state.p_pos

        # Quarterback is past line of scrimmage
        if (q_pos[1] > (line_of_scrimmage + world.first_down_line)): 
            return Q_BACK_FIRST_DOWN_LINE

        if (not q_back.in_bounds):
            return Q_BACK_NOT_IN_BOUNDS

        for d_player in d_line:
            # Check if d_player is close to q_back (ie touching, look into how to find that out)
            # If so return True
            d_pos = d_player.state.p_pos
            dist_min = q_back.size + d_player.size

            # If the quarterback and defensive player are touching, set agents to done
            if (((d_pos[0] - q_pos[0])**2 + (d_pos[1] - q_pos[1])**2)**0.5 < dist_min):
                return D_LINE_REACHED_Q_BACK

        return NOT_DONE


    # get reward for a particular agent
    def _get_reward(self, agent):
        if self.reward_callback is None:
            return 0.0
        return self.reward_callback(agent, self.world)

    # set env action for a particular agent
    def _set_action(self, action, agent, action_space, time=None):
        agent.action.u = np.zeros(self.world.dim_p)
        agent.action.c = np.zeros(self.world.dim_c)
        # process action
        if isinstance(action_space, MultiDiscrete):
            act = []
            size = action_space.high - action_space.low + 1
            index = 0
            for s in size:
                act.append(action[index:(index+s)])
                index += s
            action = act
        else:
            action = [action]

        if agent.movable:
            # physical action
            if self.discrete_action_input:
                agent.action.u = np.zeros(self.world.dim_p)
                # process discrete action
                if action[0] == 1: agent.action.u[0] = -1.0
                if action[0] == 2: agent.action.u[0] = +1.0
                if action[0] == 3: agent.action.u[1] = -1.0
                if action[0] == 4: agent.action.u[1] = +1.0
            else:
                if self.force_discrete_action:
                    d = np.argmax(action[0])
                    action[0][:] = 0.0
                    action[0][d] = 1.0
                if self.discrete_action_space:
                    agent.action.u[0] += action[0][1] - action[0][2]
                    agent.action.u[1] += action[0][3] - action[0][4]
                else:
                    agent.action.u = action[0]
            sensitivity = 5.0
            if agent.accel is not None:
                sensitivity = agent.accel
            agent.action.u *= sensitivity
            action = action[1:]
        if not agent.silent:
            # communication action
            if self.discrete_action_input:
                agent.action.c = np.zeros(self.world.dim_c)
                agent.action.c[action[0]] = 1.0
            else:
                agent.action.c = action[0]
            action = action[1:]
        # make sure we used all elements of action
        assert len(action) == 0

    # reset rendering assets
    def _reset_render(self):
        self.render_geoms = None
        self.render_geoms_xform = None

    # render environment
    def render_whole_field(self, mode='human'):
        if mode == 'human':
            alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            message = ''
            for agent in self.world.agents:
                comm = []
                for other in self.world.agents:
                    if other is agent: continue
                    if np.all(other.state.c == 0):
                        word = '_'
                    else:
                        word = alphabet[np.argmax(other.state.c)]
                    message += (other.name + ' to ' + agent.name + ': ' + word + '   ')

        # for i in range(len(self.viewers)):
        #     # create viewers (if necessary)
        #     if self.viewers[i] is None:
        #         # import rendering only if we need it (and don't import for headless machines)
        #         #from gym.envs.classic_control import rendering
        #         from multiagent import rendering
        #         self.viewers[i] = rendering.Viewer(700,700)

        if self.viewer is None:
            from multiagent import rendering
            self.viewer = rendering.Viewer(53*7, 120*7)

        # create rendering geometry
        if self.render_geoms is None:
            # import rendering only if we need it (and don't import for headless machines)
            #from gym.envs.classic_control import rendering
            from multiagent import rendering
            self.render_geoms = []
            self.render_geoms_xform = []
            for entity in self.world.entities:
                size = 2*entity.size
                # if entity.position == 'q_back':
                #     size = 2*size
                geom = rendering.make_circle(size)
                xform = rendering.Transform()
                if 'q_back' == entity.position:
                    geom.set_color(0, 1, 0, alpha=0.5)
                else:
                    geom.set_color(*entity.color)
                geom.add_attr(xform)
                self.render_geoms.append(geom)
                self.render_geoms_xform.append(xform)

            self.viewer.geoms = []
            for geom in self.render_geoms:
                self.viewer.add_geom(geom)

        line_of_scrimmage = self.world.line_of_scrimmage
        first_down_line = line_of_scrimmage + self.world.first_down_line

        self.viewer.draw_line((0, line_of_scrimmage), (53, line_of_scrimmage))
        self.viewer.draw_line((0, first_down_line), (53, first_down_line))

        results = []
        from multiagent import rendering
        # update bounds to center around agent
        cam_range = 1
        if self.shared_viewer:
            pos = np.zeros(self.world.dim_p)
        else:
            pos = self.agents[i].state.p_pos
        self.viewer.set_bounds(0, 53, 0, 120)
        # update geometry positions
        for e, entity in enumerate(self.world.entities):
            self.render_geoms_xform[e].set_translation(*entity.state.p_pos)
        # render to display or array
        results.append(self.viewer.render(return_rgb_array = mode=='rgb_array'))

        return results

    # render environment
    def render(self, mode='human'):
        if mode == 'human':
            alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            message = ''
            for agent in self.world.agents:
                comm = []
                for other in self.world.agents:
                    if other is agent: continue
                    if np.all(other.state.c == 0):
                        word = '_'
                    else:
                        word = alphabet[np.argmax(other.state.c)]
                    message += (other.name + ' to ' + agent.name + ': ' + word + '   ')

        for i in range(len(self.viewers)):
            # create viewers (if necessary)
            if self.viewers[i] is None:
                # import rendering only if we need it (and don't import for headless machines)
                #from gym.envs.classic_control import rendering
                from multiagent import rendering
                self.viewers[i] = rendering.Viewer(700,700)

        # create rendering geometry
        if self.render_geoms is None:
            # import rendering only if we need it (and don't import for headless machines)
            #from gym.envs.classic_control import rendering
            from multiagent import rendering
            self.render_geoms = []
            self.render_geoms_xform = []
            for entity in self.world.entities:
                geom = rendering.make_circle(entity.size)
                xform = rendering.Transform()
                if 'q_back' == entity.position:
                    geom.set_color(0, 1, 0, alpha=0.5)
                else:
                    geom.set_color(*entity.color)
                geom.add_attr(xform)
                self.render_geoms.append(geom)
                self.render_geoms_xform.append(xform)

            # add geoms to viewer
            for viewer in self.viewers:
                viewer.geoms = []
                for geom in self.render_geoms:
                    viewer.add_geom(geom)

        results = []
        for i in range(len(self.viewers)):
            from multiagent import rendering
            # update bounds to center around agent
            cam_range = 1
            if self.shared_viewer:
                pos = np.zeros(self.world.dim_p)
            else:
                pos = self.agents[i].state.p_pos
            self.viewers[i].set_bounds(pos[0]-cam_range,pos[0]+cam_range,pos[1]-cam_range,pos[1]+cam_range)
            # update geometry positions
            for e, entity in enumerate(self.world.entities):
                self.render_geoms_xform[e].set_translation(*entity.state.p_pos)
            # render to display or array
            results.append(self.viewers[i].render(return_rgb_array = mode=='rgb_array'))

        return results

    # create receptor field locations in local coordinate frame
    def _make_receptor_locations(self, agent):
        receptor_type = 'polar'
        range_min = 0.05 * 2.0
        range_max = 1.00
        dx = []
        # circular receptive field
        if receptor_type == 'polar':
            for angle in np.linspace(-np.pi, +np.pi, 8, endpoint=False):
                for distance in np.linspace(range_min, range_max, 3):
                    dx.append(distance * np.array([np.cos(angle), np.sin(angle)]))
            # add origin
            dx.append(np.array([0.0, 0.0]))
        # grid receptive field
        if receptor_type == 'grid':
            for x in np.linspace(-range_max, +range_max, 5):
                for y in np.linspace(-range_max, +range_max, 5):
                    dx.append(np.array([x,y]))
        return dx


# vectorized wrapper for a batch of multi-agent environments
# assumes all environments have the same observation and action space
class BatchMultiAgentEnv(gym.Env):
    metadata = {
        'runtime.vectorized': True,
        'render.modes' : ['human', 'rgb_array']
    }

    def __init__(self, env_batch):
        self.env_batch = env_batch

    @property
    def n(self):
        return np.sum([env.n for env in self.env_batch])

    @property
    def action_space(self):
        return self.env_batch[0].action_space

    @property
    def observation_space(self):
        return self.env_batch[0].observation_space

    def step(self, action_n, time):
        obs_n = []
        reward_n = []
        done_n = []
        info_n = {'n': []}
        i = 0
        for env in self.env_batch:
            obs, reward, done, _ = env.step(action_n[i:(i+env.n)], time)
            i += env.n
            obs_n += obs
            # reward = [r / len(self.env_batch) for r in reward]
            reward_n += reward
            done_n += done
        return obs_n, reward_n, done_n, info_n

    def reset(self):
        obs_n = []
        for env in self.env_batch:
            obs_n += env.reset()
        return obs_n

    # render environment
    def render(self, mode='human', close=True):
        results_n = []
        for env in self.env_batch:
            results_n += env.render(mode, close)
        return results_n
