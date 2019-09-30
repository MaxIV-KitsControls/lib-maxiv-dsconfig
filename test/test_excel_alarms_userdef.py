from os.path import dirname, abspath, join

from dsconfig.excel_alarms_userdef import xls_to_dict


def test_excel_alarms_user_def():
    xls_file = join(dirname(abspath(__file__)), 'files', 'AlarmDemoV6.xls')
    result = xls_to_dict(xls_file)
    assert result['servers']['PyAlarm/']['PyAlarm']
    alarm_prop = result['servers']['PyAlarm/mypyalarm']['PyAlarm']['Alarms/test/1']
    assert alarm_prop['properties']['AlarmSeverities'] == ['VacPressure:WARNING',
                                                           'MagCurrent:ALARM']
