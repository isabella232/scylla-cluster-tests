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

import time
import logging
import pytest

from sdcm.utils import alternator
from sdcm.ycsb_thread import YcsbStressThread
from sdcm.kcl_thread import KclStressThread, CompareTablesSizesThread
from unit_tests.dummy_remote import LocalLoaderSetDummy

pytestmark = [pytest.mark.usefixtures('events'),
              pytest.mark.skipif(True, reason="those are integration tests only")]

ALTERNATOR_PORT = 8000
TEST_PARAMS = dict(dynamodb_primarykey_type='HASH',
                   alternator_use_dns_routing=True, alternator_port=ALTERNATOR_PORT)
ALTERNATOR = alternator.api.Alternator(sct_params={"alternator_access_key_id": None,
                                                   "alternator_secret_access_key": None,
                                                   "alternator_port": ALTERNATOR_PORT})


def test_01_kcl_with_ycsb(request, docker_scylla, events):  # pylint: disable=too-many-locals
    loader_set = LocalLoaderSetDummy()
    num_of_keys = 1000
    # 1. start kcl thread and ycsb at the same time
    ycsb_cmd = f'bin/ycsb load dynamodb  -P workloads/workloada -p recordcount={num_of_keys} -p dataintegrity=true ' \
               f'-p insertorder=uniform -p insertcount={num_of_keys} -p fieldcount=2 -p fieldlength=5'
    ycsb_thread = YcsbStressThread(loader_set, ycsb_cmd, node_list=[docker_scylla], timeout=600, params=TEST_PARAMS)

    kcl_cmd = f"hydra-kcl -t usertable -k {num_of_keys}"
    kcl_thread = KclStressThread(loader_set, kcl_cmd, node_list=[docker_scylla], timeout=600, params=TEST_PARAMS)
    stress_cmd = 'table_compare interval=20; src_table="alternator_usertable".usertable; ' \
                 'dst_table="alternator_usertable-dest"."usertable-dest"'
    compare_sizes = CompareTablesSizesThread(
        loader_set=loader_set, stress_cmd=stress_cmd, node_list=[docker_scylla], timeout=600, params=TEST_PARAMS)

    def cleanup_thread():
        ycsb_thread.kill()
        kcl_thread.kill()

    request.addfinalizer(cleanup_thread)

    time.sleep(60)
    kcl_thread.run()
    time.sleep(30)
    ycsb_thread.run()

    compare_sizes.run()
    compare_sizes.get_results()

    output = ycsb_thread.get_results()
    assert 'latency mean' in output[0]
    assert float(output[0]['latency mean']) > 0

    assert 'latency 99th percentile' in output[0]
    assert float(output[0]['latency 99th percentile']) > 0

    output = kcl_thread.get_results()
    logging.debug(output)

    error_log_content_before = events.get_event_log_file('error.log')

    # 2. do read with dataintegrity=true
    cmd = f'bin/ycsb run dynamodb -P workloads/workloada -p recordcount={num_of_keys} -p insertorder=uniform ' \
          f'-p insertcount={num_of_keys} -p fieldcount=2 -p fieldlength=5 -p dataintegrity=true ' \
          f'-p operationcount={num_of_keys}'
    ycsb_thread2 = YcsbStressThread(loader_set, cmd, node_list=[docker_scylla], timeout=500, params=TEST_PARAMS)

    def cleanup_thread2():
        ycsb_thread2.kill()

    request.addfinalizer(cleanup_thread2)

    ycsb_thread2.run()
    ycsb_thread2.get_results()

    # 3. check that events with errors weren't raised
    error_log_content_after = events.get_event_log_file('error.log')
    assert error_log_content_after == error_log_content_before
