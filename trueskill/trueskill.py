#!/usr/bin/python

# Copyright 2010 Doug Zongker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Implements the player skill estimation algorithm from Herbrich et al.,
"TrueSkill(TM): A Bayesian Skill Rating System".
"""

from __future__ import print_function

__author__ = "Doug Zongker <dougz@isotropic.org>"

import sys
if sys.hexversion < 0x02060000:
  print("requires Python 2.6 or higher")
  sys.exit(1)

from scipy.stats.distributions import norm as scipy_norm
from math import sqrt

norm = scipy_norm()
pdf = norm.pdf
cdf = norm.cdf
icdf = norm.ppf    # inverse CDF

# Update rules for approximate marginals for the win and draw cases,
# respectively.

def Vwin(t, e):
  return pdf(t-e) / cdf(t-e)
def Wwin(t, e):
  return Vwin(t, e) * (Vwin(t, e) + t - e)

def Vdraw(t, e):
  return (pdf(-e-t) - pdf(e-t)) / (cdf(e-t) - cdf(-e-t))
def Wdraw(t, e):
  return Vdraw(t, e) ** 2 + ((e-t) * pdf(e-t) + (e+t) * pdf(e+t)) / (cdf(e-t) - cdf(-e-t))


class Gaussian(object):
  """
  Object representing a gaussian distribution.  Create as:

    Gaussian(mu=..., sigma=...)
      or
    Gaussian(pi=..., tau=...)
      or
    Gaussian()    # gives 0 mean, infinite sigma
  """

  def __init__(self, mu=None, sigma=None, pi=None, tau=None):
    if pi is not None:
      self.pi = pi
      self.tau = tau
    elif mu is not None:
      self.pi = sigma ** -2
      self.tau = self.pi * mu
    else:
      self.pi = 0
      self.tau = 0

  def __repr__(self):
    return "N(pi={0.pi},tau={0.tau})".format(self)

  def __str__(self):
    if self.pi == 0.0:
      return "N(mu=0,sigma=inf)"
    else:
      sigma = sqrt(1/self.pi)
      mu = self.tau / self.pi
      return "N(mu={0:.3f},sigma={1:.3f})".format(mu, sigma)

  def MuSigma(self):
    """ Return the value of this object as a (mu, sigma) tuple. """
    if self.pi == 0.0:
      return 0, float("inf")
    else:
      return self.tau / self.pi, sqrt(1/self.pi)


  def ProbabilityPositive(self):
    mu, sigma = self.MuSigma()
    return 1.0 - scipy_norm(loc=mu, scale=sigma).cdf(0.0)

  def __mul__(self, other):
    return Gaussian(pi=self.pi+other.pi, tau=self.tau+other.tau)

  def __div__(self, other):
    return Gaussian(pi=self.pi-other.pi, tau=self.tau-other.tau)

  def __add__(self, other):
    mu1, sigma1 = self.MuSigma()
    mu2, sigma2 = other.MuSigma()
    return Gaussian(mu=mu1 + mu2, sigma=sqrt(sigma1*sigma1 + sigma2*sigma2))

  def __sub__(self, other):
    mu1, sigma1 = self.MuSigma()
    mu2, sigma2 = other.MuSigma()
    return Gaussian(mu=mu1 - mu2, sigma=sqrt(sigma1*sigma1 + sigma2*sigma2))


class Variable(object):
  """ A variable node in the factor graph. """

  def __init__(self):
    self.value = Gaussian()
    self.factors = {}

  def __str__(self):
    return '%s [%s]' % (self.value, 
                        ' '.join(str(self.factors[f]) for f in self.factors))

  def AttachFactor(self, factor):
    self.factors[factor] = Gaussian()

  def UpdateMessage(self, factor, message):
    old_message = self.factors[factor]
    self.value = self.value / old_message * message
    self.factors[factor] = message

  def UpdateValue(self, factor, value):
    old_message = self.factors[factor]
    self.factors[factor] = value * old_message / self.value
    self.value = value

  def GetMessage(self, factor):
    return self.factors[factor]


class Factor(object):
  """ Base class for a factor node in the factor graph. """
  def __init__(self, variables):
    self.variables = variables
    for v in variables:
      v.AttachFactor(self)

# The following Factor classes implement the five update equations
# from Table 1 of the Herbrich et al. paper.

class PriorFactor(Factor):
  """ Connects to a single variable, pushing a fixed (Gaussian) value
  to that variable. """
  def __init__(self, variable, param):
    super(PriorFactor, self).__init__([variable])
    self.param = param

  def Start(self):
    self.variables[0].UpdateValue(self, self.param)

class LikelihoodFactor(Factor):
  """ Connects two variables, the value of one being the mean of the
  message sent to the other. """
  def __init__(self, mean_variable, value_variable, variance):
    super(LikelihoodFactor, self).__init__([mean_variable, value_variable])
    self.mean = mean_variable
    self.value = value_variable
    self.variance = variance

  def UpdateValue(self):
    """ Update the value after a change in the mean (going "down" in
    the TrueSkill factor graph. """
    y = self.mean.value
    fy = self.mean.GetMessage(self)
    a = 1.0 / (1.0 + self.variance * (y.pi - fy.pi))
    self.value.UpdateMessage(self, Gaussian(pi=a*(y.pi - fy.pi),
                                            tau=a*(y.tau - fy.tau)))

  def UpdateMean(self):
    """ Update the mean after a change in the value (going "up" in
    the TrueSkill factor graph. """

    # Note this is the same as UpdateValue, with self.mean and
    # self.value interchanged.
    x = self.value.value
    fx = self.value.GetMessage(self)
    a = 1.0 / (1.0 + self.variance * (x.pi - fx.pi))
    self.mean.UpdateMessage(self, Gaussian(pi=a*(x.pi - fx.pi),
                                           tau=a*(x.tau - fx.tau)))

class SumFactor(Factor):
  """ A factor that connects a sum variable with 1 or more terms,
  which are summed after being multiplied by fixed (real)
  coefficients. """

  def __init__(self, sum_variable, terms_variables, coeffs):
    assert len(terms_variables) == len(coeffs)
    self.sum = sum_variable
    self.terms = terms_variables
    self.coeffs = coeffs
    super(SumFactor, self).__init__([sum_variable] + terms_variables)

  def _InternalUpdate(self, var, y, fy, a):
    new_pi = 1.0 / (sum(a[j]**2 / (y[j].pi - fy[j].pi) for j in range(len(a))))
    new_tau = new_pi * sum(a[j] *
                           (y[j].tau - fy[j].tau) / (y[j].pi - fy[j].pi)
                           for j in range(len(a)))
    var.UpdateMessage(self, Gaussian(pi=new_pi, tau=new_tau))

  def UpdateSum(self):
    """ Update the sum value ("down" in the factor graph). """
    y = [t.value for t in self.terms]
    fy = [t.GetMessage(self) for t in self.terms]
    a = self.coeffs
    self._InternalUpdate(self.sum, y, fy, a)

  def UpdateTerm(self, index):
    """ Update one of the term values ("up" in the factor graph). """

    # Swap the coefficients around to make the term we want to update
    # be the 'sum' of the other terms and the factor's sum, eg.,
    # change:
    #
    #    x = y_1 + y_2 + y_3
    #
    # to
    #
    #    y_2 = x - y_1 - y_3
    #
    # then use the same update equation as for UpdateSum.

    b = self.coeffs
    a = [-b[i] / b[index] for i in range(len(b)) if i != index]
    a.insert(index, 1.0 / b[index])

    v = self.terms[:]
    v[index] = self.sum
    y = [i.value for i in v]
    fy = [i.GetMessage(self) for i in v]
    self._InternalUpdate(self.terms[index], y, fy, a)

class TruncateFactor(Factor):
  """ A factor for (approximately) truncating the team difference
  distribution based on a win or a draw (the choice of which is
  determined by the functions you pass as V and W). """

  def __init__(self, variable, V, W, epsilon):
    super(TruncateFactor, self).__init__([variable])
    self.var = variable
    self.V = V
    self.W = W
    self.epsilon = epsilon

  def Update(self):
    x = self.var.value
    fx = self.var.GetMessage(self)

    c = x.pi - fx.pi
    d = x.tau - fx.tau
    sqrt_c = sqrt(c)
    args = (d / sqrt_c, self.epsilon * sqrt_c)
    V = self.V(*args)
    W = self.W(*args)
    new_val = Gaussian(pi=c / (1.0 - W), tau=(d + sqrt_c * V) / (1.0 - W))
    self.var.UpdateValue(self, new_val)


def DrawProbability(epsilon, beta, total_players=2):
  """ Compute the draw probability given the draw margin (epsilon). """
  return 2 * cdf(epsilon / (sqrt(total_players) * beta)) - 1

def DrawMargin(p, beta, total_players=2):
  """ Compute the draw margin (epsilon) given the draw probability. """
  return icdf((p+1.0)/2) * sqrt(total_players) * beta


INITIAL_MU = 25.0
INITIAL_SIGMA = INITIAL_MU / 3.0

def SetParameters(beta=None, epsilon=None, draw_probability=None,
                  gamma=None):
  """
  Sets three global parameters used in the TrueSkill algorithm.

  beta is a measure of how random the game is.  You can think of it as
  the difference in skill (mean) needed for the better player to have
  an ~80% chance of winning.  A high value means the game is more
  random (I need to be *much* better than you to consistently overcome
  the randomness of the game and beat you 80% of the time); a low
  value is less random (a slight edge in skill is enough to win
  consistently).  The default value of beta is half of INITIAL_SIGMA
  (the value suggested by the Herbrich et al. paper).

  epsilon is a measure of how common draws are.  Instead of specifying
  epsilon directly you can pass draw_probability instead (a number
  from 0 to 1, saying what fraction of games end in draws), and
  epsilon will be determined from that.  The default epsilon
  corresponds to a draw probability of 0.1 (10%).  (You should pass a
  value for either epsilon or draw_probability, not both.)

  gamma is a small amount by which a player's uncertainty (sigma) is
  increased prior to the start of each game.  This allows us to
  account for skills that vary over time; the effect of old games
  on the estimate will slowly disappear unless reinforced by evidence
  from new games.
  """

  global BETA, EPSILON, GAMMA

  if beta is None:
    BETA = INITIAL_SIGMA * 3.0 / 2.0
  else:
    BETA = beta

  if epsilon is None:
    if draw_probability is None:
      draw_probability = 0.10
    EPSILON = DrawMargin(draw_probability, BETA)
  else:
    EPSILON = epsilon

  if gamma is None:
    GAMMA = INITIAL_SIGMA / 100.0
  else:
    GAMMA = gamma

SetParameters()

class SkillInfo:
  def __init__(self, mu, sigma, gamma):
    self.mu = mu
    self.sigma = sigma
    self.gamma = gamma
    self.floor = mu - 3*sigma
    self.ceil = mu + 3*sigma

def default_missing_func(name):
  return SkillInfo(25.0, 25./3, 25./300)

class SkillTable:
  def __init__(self, missing_func=None):
    if missing_func is None:
      missing_func = default_missing_func

    self.skill_infos = {}
    self.missing_func = missing_func
  
  def _get_skill_info(self, key):
    if key not in self.skill_infos:
      self.skill_infos[key] = self.missing_func(key)
    return self.skill_infos[key]

  def get_mu(self, player):
    return self._get_skill_info(player).mu

  def get_sigma(self, player):
    return self._get_skill_info(player).sigma

  def get_gamma(self, player):
    return self._get_skill_info(player).gamma

  def set_mu(self, player, mu):
    self._get_skill_info(player).mu = mu

  def set_sigma(self, player, sigma):
    self._get_skill_info(player).sigma = sigma
    self.update_floor_and_ceil(player)
  
  def update_floor_and_ceil(self, player):
    skill_info = self._get_skill_info(player)
    skill_info.ceil = skill_info.mu + 3*skill_info.sigma
    skill_info.floor = skill_info.mu - 3*skill_info.sigma

  def ordered_skills(self):
    return sorted(self.skill_infos.items(), key = lambda x: -x[1].mu)

def update_trueskill_team(team_results, skill_table):
  """
  Each team_result is a tuple of
  (list of player names, contributions, rank).
  The lowest rank is the winner.
  """
  team_results.sort(key=lambda t: t[2])
  players = [p for team in team_results for p in team[0]]
  
  # Create all the variable nodes in the graph.
  ss = [Variable() for p in players]
  ps = [Variable() for p in players]
  ts = [Variable() for t in team_results]
  ds = [Variable() for t in team_results[:-1]]
  
  # Create each layer of factor nodes.  At the top we have priors
  # initialized to the player's current skill estimate.
  
  skill = [PriorFactor(s, Gaussian(
        mu=skill_table.get_mu(pl),
        sigma=skill_table.get_sigma(pl) + skill_table.get_gamma(pl)))
           for (s, pl) in zip(ss, players)]
  skill_to_perf = [LikelihoodFactor(s, p, BETA**2) for (s, p) in zip(ss, ps)]
  player_counter = 0
  team_counter = 0
  perf_to_team = []
  for team, contrib, rank in team_results:
    teamsize = len(team)
    perf_to_team.append(SumFactor(ts[team_counter],
                                  ps[player_counter:player_counter+teamsize],
                                  contrib))
    player_counter += teamsize
    team_counter += 1

  team_diff = [SumFactor(d, [t1, t2], [+1, -1])
               for (d, t1, t2) in zip(ds, ts[:-1], ts[1:])]
  
  # At the bottom we connect adjacent teams with a 'win' or 'draw'
  # factor, as determined by the rank values.
  trunc = [TruncateFactor(d,
                          Vdraw if t1[2] == t2[2] else Vwin,
                          Wdraw if t1[2] == t2[2] else Wwin,
                          EPSILON)
           for (d, t1, t2) in zip(ds, team_results[:-1], team_results[1:])]
  
  # Start evaluating the graph by pushing messages 'down' from the
  # priors.

  for f in skill:
    f.Start()
  for f in skill_to_perf:
    f.UpdateValue()
    #print("updating skill to perf: %s" % str(f.value))
  for f in perf_to_team:
    f.UpdateSum()

  # Because the truncation factors are approximate, we iterate,
  # adjusting the team performance (t) and team difference (d)
  # variables until they converge.  In practice this seems to happen
  # very quickly, so I just do a fixed number of iterations.
  #
  # This order of evaluation is given by the numbered arrows in Figure
  # 1 of the Herbrich paper.

  #p0v = perf_to_team[0].sum.value
  #p1v = perf_to_team[1].sum.value
  #diff_p0p1 = p0v - p1v
  #print('team perfs %s %s, diff %s' %  (p0v, p1v, diff_p0p1))
  #print('%.3f' % diff_p0p1.ProbabilityPositive())

  for i in range(5):
    for f in team_diff:
      f.UpdateSum()             # arrows (1) and (4)
      #print('team  %.3f, %s' % (f.sum.value.ProbabilityPositive(), players))

    for f in trunc: 
      f.Update()                # arrows (2) and (5)
      #print('trunc %.3f'  % (f.var.value.ProbabilityPositive()))
    for f in team_diff:
      f.UpdateTerm(0)           # arrows (3) and (6)
      f.UpdateTerm(1)

  # Now we push messages back up the graph, from the teams back to the
  # player skills.

  for f in perf_to_team:
    for t in xrange(len(f.terms)):
      f.UpdateTerm(t)
  for f in skill_to_perf:
    f.UpdateMean()

  # Finally, the players' new skills are the new values of the s
  # variables.

  for s, pl in zip(ss, players):
    mu, sigma = s.value.MuSigma()
    skill_table.set_mu(pl, mu)
    skill_table.set_sigma(pl, sigma)


def AdjustPlayers(players):
  """
  Adjust the skills of a list of players.

  'players' is a list of player objects, for all the players who
  participated in a single game.  A 'player object' is any object with
  a "skill" attribute (a (mu, sigma) tuple) and a "rank" attribute.
  Lower ranks are better; the lowest rank is the overall winner of the
  game.  Equal ranks mean that the two players drew.

  This function updates all the "skill" attributes of the player
  objects to reflect the outcome of the game.  The input list is not
  altered.
  """

  players = players[:]
  # Sort players by rank, the factor graph will connect adjacent team
  # performance variables.
  players.sort(key=lambda p: p.rank)

  # Create all the variable nodes in the graph.  "Teams" are each a
  # single player; there's a one-to-one correspondence between players
  # and teams.  (It would be straightforward to make multiplayer
  # teams, but it's not needed for my current purposes.)
  ss = [Variable() for p in players]
  ps = [Variable() for p in players]
  ts = [Variable() for p in players]
  ds = [Variable() for p in players[:-1]]

  # Create each layer of factor nodes.  At the top we have priors
  # initialized to the player's current skill estimate.
  skill = [PriorFactor(s, Gaussian(mu=pl.skill[0],
                                   sigma=pl.skill[1] + GAMMA))
           for (s, pl) in zip(ss, players)]
  skill_to_perf = [LikelihoodFactor(s, p, BETA**2)
                   for (s, p) in zip(ss, ps)]
  perf_to_team = [SumFactor(t, [p], [1])
                  for (p, t) in zip(ps, ts)]
  team_diff = [SumFactor(d, [t1, t2], [+1, -1])
               for (d, t1, t2) in zip(ds, ts[:-1], ts[1:])]
  # At the bottom we connect adjacent teams with a 'win' or 'draw'
  # factor, as determined by the rank values.
  trunc = [TruncateFactor(d,
                          Vdraw if pl1.rank == pl2.rank else Vwin,
                          Wdraw if pl1.rank == pl2.rank else Wwin,
                          EPSILON)
           for (d, pl1, pl2) in zip(ds, players[:-1], players[1:])]

  # Start evaluating the graph by pushing messages 'down' from the
  # priors.

  for f in skill:
    f.Start()
  for f in skill_to_perf:
    f.UpdateValue()
  for f in perf_to_team:
    f.UpdateSum()

  # Because the truncation factors are approximate, we iterate,
  # adjusting the team performance (t) and team difference (d)
  # variables until they converge.  In practice this seems to happen
  # very quickly, so I just do a fixed number of iterations.
  #
  # This order of evaluation is given by the numbered arrows in Figure
  # 1 of the Herbrich paper.

  for i in range(5):
    for f in team_diff:
      f.UpdateSum()             # arrows (1) and (4)
    for f in trunc:
      f.Update()                # arrows (2) and (5)
    for f in team_diff:
      f.UpdateTerm(0)           # arrows (3) and (6)
      f.UpdateTerm(1)

  # Now we push messages back up the graph, from the teams back to the
  # player skills.

  for f in perf_to_team:
    f.UpdateTerm(0)
  for f in skill_to_perf:
    f.UpdateMean()

  # Finally, the players' new skills are the new values of the s
  # variables.

  for s, pl in zip(ss, players):
    pl.skill = s.value.MuSigma()

__all__ = ["AdjustPlayers", "SetParameters", "INITIAL_MU", "INITIAL_SIGMA"]
