#!/usr/bin/env python

import argparse
import logging

import pebble as libpebble
from pebble.PblCommand          import PblCommand
from pebble.PblProjectCreator   import PblProjectCreator
from pebble.PblBuildCommand     import PblBuildCommand
from pebble.LibPebblesCommand   import *


class PbSDKShell:
  commands = []

  def __init__(self):
    self.commands.append(PblProjectCreator())
    self.commands.append(PblBuildCommand())
    self.commands.append(PblInstallCommand())
    self.commands.append(PblPingCommand())

  def main(self):
    logging.basicConfig(format='[%(levelname)-8s] %(message)s', level = logging.WARNING)

    parser = argparse.ArgumentParser(description = 'Pebble SDK Shell')
    parser.add_argument('--debug', action="store_true", help="Enable debugging output")
    subparsers = parser.add_subparsers(dest="command", title="Command", description="Action to perform")
    for command in self.commands:
      subparser = subparsers.add_parser(command.name, help = command.help)
      command.configure_subparser(subparser)
    args = parser.parse_args()

    self.run_action(args.command, args)

  def run_action(self, action, args):
    # Find the extension that was called
    command = [x for x in self.commands if x.name == args.command][0]

    try:
        command.run(args)
    except libpebble.PebbleError as e:
        if args.debug:
            raise e
        else:
            logging.error(e)

if __name__ == '__main__':
  PbSDKShell().main()

