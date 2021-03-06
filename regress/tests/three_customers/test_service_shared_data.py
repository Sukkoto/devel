#!/usr/bin/env python
# test_service_shared_data.py
#
# Copyright (C) 2008 Veselin Penev  https://bitdust.io
#
# This file (test_service_shared_data.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com

import os
import pytest

from testsupport import request_get, request_put, run_ssh_command_and_wait
from keywords import supplier_list_v1, share_create_v1, file_upload_start_v1, file_download_start_v1, \
    service_info_v1, file_create_v1, transfer_list_v1, packet_list_v1


def test_customer_1_share_file_to_customer_2_same_name_as_existing():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)
    supplier_list_v1('customer-2', expected_min_suppliers=4, expected_max_suppliers=4)

    service_info_v1('customer-1', 'service_shared_data', 'ON')
    service_info_v1('customer-2', 'service_shared_data', 'ON')

    # create shares (logic unit to upload/download/share files)
    share_id_customer_1 = share_create_v1('customer-1')
    share_id_customer_2 = share_create_v1('customer-2')

    filename = 'cat.txt'
    virtual_filename = filename

    volume_customer_1 = '/customer_1'
    filepath_customer_1 = f'{volume_customer_1}/{filename}'

    volume_customer_2 = '/customer_2'
    filepath_customer_2 = f'{volume_customer_2}/{filename}'

    run_ssh_command_and_wait('customer-1', f'echo customer_1 > {filepath_customer_1}')
    run_ssh_command_and_wait('customer-2', f'echo customer_2 > {filepath_customer_2}')

    remote_path_customer_1 = f'{share_id_customer_1}:{virtual_filename}'
    remote_path_customer_2 = f'{share_id_customer_2}:{virtual_filename}'

    # create virtual file for customer_1
    file_create_v1('customer-1', remote_path_customer_1)

    # create virtual file for customer_2
    file_create_v1('customer-2', remote_path_customer_2)

    # upload file for customer_1
    service_info_v1('customer-1', 'service_shared_data', 'ON')
    file_upload_start_v1('customer-1', remote_path_customer_1, filepath_customer_1)

    # upload file for customer_2
    service_info_v1('customer-2', 'service_shared_data', 'ON')
    file_upload_start_v1('customer-2', remote_path_customer_2, filepath_customer_2)

    packet_list_v1('customer-2', wait_all_finish=True)

    transfer_list_v1('customer-2', wait_all_finish=True)

    # wait for quite a while to allow files to be uploaded
    # time.sleep(5)

    service_info_v1('customer-1', 'service_shared_data', 'ON')
    file_download_start_v1('customer-1', remote_path=remote_path_customer_1, destination=volume_customer_1)

    service_info_v1('customer-2', 'service_shared_data', 'ON')
    file_download_start_v1('customer-2', remote_path=remote_path_customer_2, destination=volume_customer_2)

    service_info_v1('customer-2', 'service_shared_data', 'ON')

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    packet_list_v1('customer-2', wait_all_finish=True)

    transfer_list_v1('customer-2', wait_all_finish=True)

    response = request_put('customer-1', 'share/grant/v1',
        json={
            'trusted_global_id': 'customer-2@id-a_8084',
            'key_id': share_id_customer_1,
        },
        timeout=40,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/grant/v1 trusted_global_id=%s key_id=%s : %s\n' % ('customer-2@id-a_8084', share_id_customer_1, response.json(),))

    response = request_get('customer-2', 'file/list/all/v1')
    assert response.status_code == 200, response.json()

    run_ssh_command_and_wait('customer-2', f'mkdir {volume_customer_2}/sharesamename')
    run_ssh_command_and_wait('customer-2', f'mkdir {volume_customer_2}/sharesamename2')

    service_info_v1('customer-2', 'service_shared_data', 'ON')
    file_download_start_v1('customer-2', remote_path=remote_path_customer_1, destination=f'{volume_customer_2}/sharesamename')

    service_info_v1('customer-2', 'service_shared_data', 'ON')
    file_download_start_v1('customer-2', remote_path=remote_path_customer_2, destination=f'{volume_customer_2}/sharesamename2')

    file_1 = run_ssh_command_and_wait('customer-2', f'cat {volume_customer_2}/sharesamename/cat.txt')[0].strip()
    file_2 = run_ssh_command_and_wait('customer-2', f'cat {volume_customer_2}/sharesamename2/cat.txt')[0].strip()

    assert file_1 != file_2


def test_customer_1_share_file_to_customer_3():
    if os.environ.get('RUN_TESTS', '1') == '0':
        return pytest.skip()  # @UndefinedVariable

    supplier_list_v1('customer-1', expected_min_suppliers=2, expected_max_suppliers=2)

    key_id = share_create_v1('customer-1')

    # create randomized file to test files upload/download
    origin_volume = '/customer_1'
    origin_filename = 'second_file_customer_1.txt'
    run_ssh_command_and_wait('customer-1', f'python -c "import os, base64; print(base64.b64encode(os.urandom(24)).decode())" > {origin_volume}/{origin_filename}')

    local_path = '%s/%s' % (origin_volume, origin_filename)
    virtual_file = 'second_virtual_file.txt'
    remote_path = '%s:%s' % (key_id, virtual_file)
    download_volume = '/customer_3'
    downloaded_file = '%s/%s' % (download_volume, virtual_file)

    service_info_v1('customer-1', 'service_shared_data', 'ON')

    file_create_v1('customer-1', remote_path)

    file_upload_start_v1('customer-1', remote_path, local_path)

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    file_download_start_v1('customer-1', remote_path=remote_path, destination='/customer_1')

    packet_list_v1('customer-1', wait_all_finish=True)

    transfer_list_v1('customer-1', wait_all_finish=True)

    service_info_v1('customer-3', 'service_shared_data', 'ON')

    packet_list_v1('customer-3', wait_all_finish=True)

    transfer_list_v1('customer-3', wait_all_finish=True)

    response = request_put('customer-1', 'share/grant/v1',
        json={
            'trusted_global_id': 'customer-3@id-a_8084',
            'key_id': key_id,
        },
        timeout=40,
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'OK', response.json()
    print('\n\nshare/grant/v1 trusted_global_id=%s key_id=%s : %s\n' % ('customer-3@id-a_8084', key_id, response.json(), ))

    file_download_start_v1('customer-3', remote_path=remote_path, destination=download_volume)

    local_file_src = run_ssh_command_and_wait('customer-1', 'cat %s' % local_path)[0].strip()
    print('customer-1: file %s is %d bytes long' % (local_path, len(local_file_src)))

    downloaded_file_src = run_ssh_command_and_wait('customer-3', 'cat %s' % downloaded_file)[0].strip()
    print('customer-3: file %s is %d bytes long' % (downloaded_file, len(downloaded_file_src)))

    assert local_file_src == downloaded_file_src, "source file and shared file content is not equal"
