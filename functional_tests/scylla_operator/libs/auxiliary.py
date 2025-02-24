#!/usr/bin/env python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright (c) 2021 ScyllaDB
import os

from sdcm.cluster_k8s import ScyllaPodCluster
from sdcm.tester import ClusterTester


SCT_ROOT = os.path.realpath(os.path.join(__file__, '..', '..', '..', '..'))


class ScyllaOperatorFunctionalClusterTester(ClusterTester):
    db_cluster: ScyllaPodCluster
    test_data: dict = {}
    healthy_flag: bool = True

    def get_email_data(self):
        self.log.info("Prepare data for email")
        email_data = self._get_common_email_data()
        email_data.update({
            "test_statuses": self.test_data,
            "scylla_ami_id": self.params.get("ami_id_db_scylla") or "-", }
        )
        return email_data

    def update_test_status(self, test_name, status, error=None):
        self.test_data[test_name] = (status, error)

    def get_test_failures(self):
        pass

    def get_test_status(self):
        for _, test_data in self.test_data.items():
            if test_data[0] != 'SUCCESS':
                return 'FAILED'
        return 'SUCCESS'


def sct_abs_path(relative_filename=""):
    return os.path.join(SCT_ROOT, relative_filename)
