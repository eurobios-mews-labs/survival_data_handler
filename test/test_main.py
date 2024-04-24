# Copyright 2024 Eurobios
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import pandas as pd
import pytest
from lifelines import CoxPHFitter
from lifelines.datasets import load_rossi

from survival_data_handler.main import SurvivalEstimation, Lifespan
from survival_data_handler.utils import smooth, process_survival_function, \
    compute_derivative, test_is_survival_curves


@pytest.fixture()
def data():
    rossi = load_rossi()
    cph = CoxPHFitter()
    cph.fit(rossi, duration_col='week', event_col='arrest')
    curves = cph.predict_survival_function(rossi).T
    curves.columns = pd.to_timedelta(curves.columns.to_numpy() * 7, unit="D")
    return rossi, curves


def test_utils_smooth(data):
    _, curves = data
    ret = smooth(curves, freq="7D")
    assert all(abs(ret - curves) < 1)


def test_utils_process(data):
    _, curves = data
    ret = process_survival_function(curves)
    assert all(pd.DataFrame(ret == curves))
    curves.iloc[:, 1] = 1
    ret = process_survival_function(curves)
    assert any(pd.DataFrame(ret == curves))


def test_utils_compute_derivative(data):
    _, curves = data
    unit = pd.to_timedelta(7, unit="D").total_seconds()
    ret = compute_derivative(curves, unit)
    assert all(pd.DataFrame(ret < 0))


def test_survival_estimation(data):
    _, curves = data
    se = SurvivalEstimation(
        curves.drop_duplicates(), unit='D',
        n_unit=365.25)
    se.plot_residual_life()
    # se.plot_residual_life(mean_behaviour=False)


def test_survival_estimation_attributes(data):
    rossi, curves = data

    rossi["index"] = rossi.index
    se = SurvivalEstimation(survival_curves=curves)
    assert hasattr(se, "hazard_interp")


def test_lifespan(data):
    rossi, curves = data

    age = pd.to_timedelta(rossi["age"] * 365.25, unit="D")
    birth = pd.to_datetime('2000')
    rossi["index"] = rossi.index
    lifespan = Lifespan(
        curves,
        index=rossi["index"],
        birth=birth,
        age=age,
        window=(pd.to_datetime("2000"), pd.to_datetime("2100"))
    )

    # test plot function
    lifespan.plot_curves_residual_life()
    lifespan.plot_curves()
    lifespan.add_supervision(event=rossi["arrest"],
                             durations=pd.to_timedelta(rossi["week"] * 7, unit="D"))

    assert isinstance(lifespan.survival_function, pd.DataFrame)
    assert isinstance(lifespan.residual_survival(pd.to_datetime("2022")), pd.DataFrame)
    assert isinstance(lifespan.percentile_life(0.1), pd.DataFrame)
    assert isinstance(lifespan.residual_expected_life, pd.DataFrame)
    t = lifespan.compute_times(p=0.5)
    rossi["times"] = t


def test_supervision(data):
    rossi, curves = data
    rossi["duration"] = pd.to_timedelta(rossi["week"]*7, unit="D")
    age = pd.to_timedelta(rossi["age"] * 365.25, unit="D")
    birth = pd.to_datetime('2000')
    rossi["index"] = rossi.index
    lifespan = Lifespan(
        curves,
        index=rossi["index"],
        birth=birth,
        age=age,
        window=(pd.to_datetime("2000"), pd.to_datetime("2001"))
    )
    lifespan.add_supervision(durations=rossi["duration"] + birth, event=rossi["arrest"])
    lifespan.plot_tagged_sample(lifespan.survival_function, )
    lifespan.compute_confusion_matrix(on="survival_function", threshold=0.2)
    test_is_survival_curves(lifespan.survival_function)
