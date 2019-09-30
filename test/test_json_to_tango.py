from os.path import dirname, abspath, join
from mock import MagicMock, patch

from dsconfig.json2tango import json_to_tango


def test_json_to_tango(capsys):
    json_data_file = join(dirname(abspath(__file__)), 'files', 'json_sample_db.json')

    args = [json_data_file]

    options = MagicMock()
    options.write = False
    options.update = False
    options.case_sensitive = True
    options.verbose = True
    options.output = False
    options.input = False
    options.dbcalls = True
    options.validate = True
    options.sleep = 0.0
    options.no_colors = True
    options.include = []
    options.exclude = ['server:SOMESERVER']
    options.nostrictcheck = False
    options.include_classes = []
    options.exclude_classes = ['class:SOMECLASS']
    options.dbdata = False

    with patch('dsconfig.json2tango.PyTango'):
        with patch('dsconfig.json2tango.get_db_data') as mocked_get_db_data:
            try:
                json_to_tango(options, args)
            except SystemExit: # The script exits with SystemExit even when successful
                assert mocked_get_db_data.call_count == 1
                captured = capsys.readouterr()

                # stderr spot checks
                assert 'Summary:' in captured.err
                assert 'Add 49 servers.' in captured.err
                assert 'Add 121 devices to 49 servers.' in captured.err
                assert 'Add/change 207 device properties in 121 devices.' in captured.err
                assert '108 device attribute properties in 51 devices.' in captured.err
                assert 'Add/change 6 class properties.' in captured.err
                assert 'Add/change 6 class attribute properties' in captured.err

                # stdout spot checks
                assert "+ Device: GROW/RELATE/RICH-8" in captured.out
                assert "Server: JobOfficer/X" in captured.out
                assert "  Class: Individual" in captured.out
                assert "  Properties:" in captured.out
                assert "    + PartnerTell" in captured.out
