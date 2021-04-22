# -*- coding: utf-8 -*-

import platform

import backoff
import requests
from singer import metrics

from .error import SailthruClient429Error, SailthruClientError, SailthruServer5xxError
from .response import SailthruResponse


def flatten_nested_hash(hash_table):
    """
    Flatten nested dictionary for GET / POST / DELETE API request
    """
    def flatten(hash_table, brackets=True):
        f = {}
        for key, value in hash_table.items():
            _key = '[' + str(key) + ']' if brackets else str(key)
            if isinstance(value, dict):
                for k, v in flatten(value).items():
                    f[_key + k] = v
            elif isinstance(value, list):
                temp_hash = {}
                for i, v in enumerate(value):
                    temp_hash[str(i)] = v
                for k, v in flatten(temp_hash).items():
                    f[_key + k] = v
            else:
                f[_key] = value
        return f
    return flatten(hash_table, False)

@backoff.on_exception(backoff.expo, SailthruClient429Error, max_tries=5, factor=2)
def sailthru_http_request(url, data, method, file_data=None, headers=None, request_timeout=10):
    """
    Perform an HTTP GET / POST / DELETE request
    """
    data = flatten_nested_hash(data)
    method = method.upper()
    params, data = (None, data) if method == 'POST' else (data, None)
    sailthru_headers = {'User-Agent': 'Sailthru API Python Client %s; Python Version: %s' % ('2.3.5', platform.python_version())}
    if headers and isinstance(headers, dict):
        for key, value in sailthru_headers.items():
            headers[key] = value
    else:
        headers = sailthru_headers
    try:
        with metrics.http_request_timer(url) as timer:
            response = requests.request(method, url, params=params, data=data, files=file_data, headers=headers, timeout=request_timeout)
            timer.tags[metrics.Tag.http_status_code] = response.status_code

        if response.status_code == 429:
            raise SailthruClient429Error
        elif response.status_code >= 500:
            raise SailthruServer5xxError

        return SailthruResponse(response)

    except requests.HTTPError as e:
        raise SailthruClientError(str(e))
    except requests.RequestException as e:
        raise SailthruClientError(str(e))
