import sys
import logging
from .penv import Env


if __name__ == '__main__':
    env = Env()
    step = 0

    while True:
        observation = env.reset()

        while True:
            action = env.brain.choose_action(observation)
            try:
                observation_ = env.step(action)
                observation = observation_

                step += 1

                if step >= 5000 and step % 5 == 0:
                    env.brain.learn()

            except Exception as e:
                print(e)
                logging.exception(e)
                sys.exit(0)

    print('game over')
    env.destroy()

