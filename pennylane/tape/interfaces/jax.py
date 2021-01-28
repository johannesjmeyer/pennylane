# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
This module contains the mixin interface class for creating differentiable quantum tapes with
JAX.
"""
from functools import partial
import jax
import jax.experimental.host_callback as host_callback
import jax.numpy as jnp
from pennylane.tape.queuing import AnnotatedQueue
from pennylane.operation import Variance, Expectation


class JAXInterface(AnnotatedQueue):
    """Mixin class for applying an JAX interface to a :class:`~.JacobianTape`.

    JAX-compatible quantum tape classes can be created via subclassing:

    .. code-block:: python

        class MyAutogradQuantumTape(AutogradInterface, JacobianTape):

    Alternatively, the jax interface can be dynamically applied to existing
    quantum tapes via the :meth:`~.apply` class method. This modifies the
    tape **in place**.

    Once created, the autograd interface can be used to perform quantum-classical
    differentiable programming.

    .. note::

        If using a device that supports native autograd computation and backpropagation, such as
        :class:`~.DefaultQubitJAX`, the Autograd interface **does not need to be applied**. It
        is only applied to tapes executed on non-JAX compatible devices.

    **Example**

    Once a JAX quantum tape has been created, it can be differentiated using JAX:

    .. code-block:: python

        tape = JAXInterface.apply(JacobianTape())

        with tape:
            qml.Rot(0, 0, 0, wires=0)
            expval(qml.PauliX(0))

        def cost_fn(x, y, z, device):
            tape.set_parameters([x, y ** 2, y * np.sin(z)], trainable_only=False)
            return tape.execute(device=device)

    >>> x = jnp.array(0.1, requires_grad=False)
    >>> y = jnp.array(0.2, requires_grad=True)
    >>> z = jnp.array(0.3, requires_grad=True)
    >>> dev = qml.device("default.qubit", wires=2)
    >>> cost_fn(x, y, z, device=dev)
    [0.03991951]
    >>> jac_fn = jax.vjp(cost_fn)
    >>> jac_fn(x, y, z, device=dev)
    DeviceArray[[ 0.39828408, -0.00045133]]
    """

    # pylint: disable=attribute-defined-outside-init
    dtype = jnp.float64

    @property
    def interface(self):  # pylint: disable=missing-function-docstring
        return "jax"

    def _execute(self, params, device):
        # TODO(chase): Add support for this.
        if len(self.observables) != 1:
            raise ValueError("Only one return type is supported currently")
        return_type = self.observables[0].return_type
        if return_type is not Variance and return_type is not Expectation:
            raise ValueError(
                f"Only Variance and Expectation returns are support, given {return_type}"
            )
        exec_fn = partial(self.execute_device, device=device)

        return host_callback.call(
            exec_fn, params, result_shape=jax.ShapeDtypeStruct((1,), JAXInterface.dtype)
        )

    @classmethod
    def apply(cls, tape):
        """Apply the JAX interface to an existing tape in-place.

        Args:
            tape (.JacobianTape): a quantum tape to apply the JAX interface to

        **Example**

        >>> with JacobianTape() as tape:
        ...     qml.RX(0.5, wires=0)
        ...     expval(qml.PauliZ(0))
        >>> JAXInterface.apply(tape)
        >>> tape
        <JAXQuantumTape: wires=<Wires = [0]>, params=1>
        """
        tape_class = getattr(tape, "__bare__", tape.__class__)
        tape.__bare__ = tape_class
        tape.__class__ = type("JAXQuantumTape", (cls, tape_class), {})
        return tape