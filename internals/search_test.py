# Copyright 2021 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import testing_config  # Must be imported before the module under test.

import datetime
from unittest import mock

from internals import models
from internals import notifier
from internals import search


class SearchFunctionsTest(testing_config.CustomTestCase):

  def setUp(self):
    self.feature_1 = models.Feature(
        name='feature 1', summary='sum', category=1, visibility=1,
        standardization=1, web_dev_views=1, impl_status_chrome=3)
    self.feature_1.owner = ['owner@example.com']
    self.feature_1.put()
    self.feature_2 = models.Feature(
        name='feature 2', summary='sum', category=2, visibility=1,
        standardization=1, web_dev_views=1, impl_status_chrome=3)
    self.feature_2.owner = ['owner@example.com']
    self.feature_2.put()
    notifier.FeatureStar.set_star(
        'starrer@example.com', self.feature_1.key.integer_id())

  def tearDown(self):
    notifier.FeatureStar.set_star(
        'starrer@example.com', self.feature_1.key.integer_id(),
        starred=False)
    self.feature_1.key.delete()
    self.feature_2.key.delete()

  @mock.patch('internals.models.Approval.get_approvals')
  @mock.patch('internals.approval_defs.fields_approvable_by')
  def test_process_pending_approval_me_query__none(
      self, mock_approvable_by, mock_get_approvals):
    """Nothing is pending."""
    testing_config.sign_in('oner@example.com', 111)
    now = datetime.datetime.now()
    mock_approvable_by.return_value = set()
    mock_get_approvals.return_value = []

    feature_ids = search.process_pending_approval_me_query()

    self.assertEqual(0, len(feature_ids))

  @mock.patch('internals.models.Approval.get_approvals')
  @mock.patch('internals.approval_defs.fields_approvable_by')
  def test_process_pending_approval_me_query__some__nonapprover(
      self, mock_approvable_by, mock_get_approvals):
    """It's not a pending approval for you."""
    testing_config.sign_in('visitor@example.com', 111)
    now = datetime.datetime.now()
    mock_approvable_by.return_value = set()
    mock_get_approvals.return_value = [
        models.Approval(
            feature_id=self.feature_1.key.integer_id(),
            field_id=1, state=0, set_on=now)]

    feature_ids = search.process_pending_approval_me_query()

    self.assertEqual(0, len(feature_ids))

  @mock.patch('internals.models.Approval.get_approvals')
  @mock.patch('internals.approval_defs.fields_approvable_by')
  def test_process_pending_approval_me_query__some__approver(
      self, mock_approvable_by, mock_get_approvals):
    """We can return a list of features pending approval."""
    testing_config.sign_in('owner@example.com', 111)
    time_1 = datetime.datetime.now() - datetime.timedelta(days=4)
    time_2 = datetime.datetime.now()
    mock_approvable_by.return_value = set([1, 2, 3])
    mock_get_approvals.return_value = [
        models.Approval(
            feature_id=self.feature_2.key.integer_id(),
            field_id=1, state=0, set_on=time_1),
        models.Approval(
            feature_id=self.feature_1.key.integer_id(),
            field_id=1, state=0, set_on=time_2),
    ]

    feature_ids = search.process_pending_approval_me_query()
    self.assertEqual(2, len(feature_ids))
    # Results are sorted by set_on timestamp.
    self.assertEqual(
        [self.feature_2.key.integer_id(),
         self.feature_1.key.integer_id()],
        feature_ids)

  def test_process_starred_me_query__anon(self):
    """Anon always has an empty list of starred features."""
    testing_config.sign_out()
    actual = search.process_starred_me_query()
    self.assertEqual(actual, [])

  def test_process_starred_me_query__none(self):
    """We can return a list of features starred by the user."""
    testing_config.sign_in('visitor@example.com', 111)
    actual = search.process_starred_me_query()
    self.assertEqual(actual, [])

  def test_process_starred_me_query__some(self):
    """We can return a list of features starred by the user."""
    testing_config.sign_in('starrer@example.com', 111)
    actual = search.process_starred_me_query()
    self.assertEqual(len(actual), 1)
    self.assertEqual(actual[0], self.feature_1.key.integer_id())

  def test_process_owner_me_query__none(self):
    """We can return a list of features owned by the user."""
    testing_config.sign_in('visitor@example.com', 111)
    actual = search.process_owner_me_query()
    self.assertEqual(actual, [])

  def test_process_owner_me_query__some(self):
    """We can return a list of features owned by the user."""
    testing_config.sign_in('owner@example.com', 111)
    actual = search.process_owner_me_query()
    self.assertEqual(len(actual), 2)
    self.assertEqual(actual[0], self.feature_1.key.integer_id())
    self.assertEqual(actual[1], self.feature_2.key.integer_id())

  @mock.patch('internals.models.Approval.get_approvals')
  @mock.patch('internals.approval_defs.fields_approvable_by')
  def test_process_recent_reviews_query__none(
      self, mock_approvable_by, mock_get_approvals):
    """Nothing has been reviewed recently."""
    mock_approvable_by.return_value = set({1, 2, 3})
    mock_get_approvals.return_value = []

    actual = search.process_recent_reviews_query()

    self.assertEqual(0, len(actual))

  @mock.patch('internals.models.Approval.get_approvals')
  @mock.patch('internals.approval_defs.fields_approvable_by')
  def test_process_recent_reviews_query__some(
      self, mock_approvable_by, mock_get_approvals):
    """Some features have been reviewed recently."""
    mock_approvable_by.return_value = set({1, 2, 3})
    time_1 = datetime.datetime.now() - datetime.timedelta(days=4)
    time_2 = datetime.datetime.now()
    mock_get_approvals.return_value = [
        models.Approval(
            feature_id=self.feature_1.key.integer_id(),
            field_id=1, state=models.Approval.NA, set_on=time_2),
        models.Approval(
            feature_id=self.feature_2.key.integer_id(),
            field_id=1, state=models.Approval.APPROVED, set_on=time_1),
    ]

    actual = search.process_recent_reviews_query()

    self.assertEqual(2, len(actual))
    self.assertEqual(actual[0], self.feature_1.key.integer_id())  # Most recent
    self.assertEqual(actual[1], self.feature_2.key.integer_id())

  @mock.patch('internals.search.process_pending_approval_me_query')
  @mock.patch('internals.search.process_starred_me_query')
  @mock.patch('internals.search.process_owner_me_query')
  @mock.patch('internals.search.process_recent_reviews_query')
  def test_process_query__predefined(
      self, mock_recent, mock_own_me, mock_star_me, mock_pend_me):
    """We can match predefined queries."""
    mock_recent.return_value = [self.feature_1.key.integer_id()]
    mock_own_me.return_value = [self.feature_2.key.integer_id()]
    mock_star_me.return_value = [self.feature_1.key.integer_id()]
    mock_pend_me.return_value = [self.feature_2.key.integer_id()]

    actual_pending = search.process_query('pending-approval-by:me')
    self.assertEqual(actual_pending[0]['name'], 'feature 2')

    actual_star_me = search.process_query('starred-by:me')
    self.assertEqual(actual_star_me[0]['name'], 'feature 1')

    actual_own_me = search.process_query('owner:me')
    self.assertEqual(actual_own_me[0]['name'], 'feature 2')

    actual_recent = search.process_query('is:recently-reviewed')
    self.assertEqual(actual_recent[0]['name'],'feature 1')

  def test_process_query__single_field(self):
    """We can can run single-field queries."""

    actual = search.process_query('category=1')
    self.assertEqual(1, len(actual))
    self.assertEqual(actual[0]['name'], 'feature 1')

    actual = search.process_query('category=2')
    self.assertEqual(1, len(actual))
    self.assertEqual(actual[0]['name'], 'feature 2')

    actual = search.process_query('browsers.webdev.view=1')
    self.assertEqual(2, len(actual))
    self.assertCountEqual(
        [f['name'] for f in actual],
        ['feature 1', 'feature 2'])


  @mock.patch('logging.warning')
  def test_process_query__bad(self, mock_warn):
    """Query terms that are not predefined or field-op-value, give warnings."""
    self.assertEqual(
        search.process_query('anything else'),
        [])
    self.assertEqual(2, len(mock_warn.mock_calls))
