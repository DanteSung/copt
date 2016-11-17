import warnings
import numpy as np
from scipy import optimize
from scipy import linalg


def three_split(
        f, f_prime, g_prox, h_prox, y0, alpha=1.0, beta=1.0, tol=1e-6, max_iter=1000,
        g_prox_args=(), h_prox_args=(),
        verbose=0, callback=None, backtracking=True, step_size=1., max_iter_backtracking=100,
        backtracking_factor=0.4):
    """
    Davis-Yin three operator splitting schem for optimization problems of the form

               minimize_x f(x) + alpha * g(x) + beta * h(x)

    where f is a smooth function and g is a (possibly non-smooth)
    function for which the proximal operator is known.

    Parameters
    ----------
    f : callable
        f(x) returns the value of f at x.

    f_prime : callable or None
        f_prime(x) returns the gradient of f.

    g_prox : callable or None
        g_prox(x, alpha, *args) returns the proximal operator of g at xa
        with parameter alpha. Extra arguments can be passed by g_prox_args.

    y0 : array-like
        Initial guess

    backtracking : boolean
        Whether to perform backtracking (i.e. line-search) to estimate
        the step size.

    max_iter : int
        Maximum number of iterations.

    verbose : int
        Verbosity level, from 0 (no output) to 2 (output on each iteration)

    step_size : float
        Starting value for the line-search procedure.

    callback : callable
        callback function (optional).

    Returns
    -------
    res : OptimizeResult
        The optimization result represented as a
        ``scipy.optimize.OptimizeResult`` object. Important attributes are:
        ``x`` the solution array, ``success`` a Boolean flag indicating if
        the optimizer exited successfully and ``message`` which describes
        the cause of the termination. See `scipy.optimize.OptimizeResult`
        for a description of other attributes.

    References
    ----------
    Davis, Damek, and Wotao Yin. "A three-operator splitting scheme and its optimization applications."
    arXiv preprint arXiv:1504.01032 (2015).
    """
    yk = np.array(y0, copy=True)
    success = False
    if not max_iter_backtracking > 0:
        raise ValueError('Line search iterations need to be greater than 0')

    if g_prox is None:
        def g_prox(x, step_size, *args): return x
    if h_prox is None:
        def h_prox(x, step_size, *args): return x
    it = 1
    # .. a while loop instead of a for loop ..
    # .. allows for infinite or floating point max_iter ..
    while it <= max_iter:
        current_step_size = step_size
        xk = g_prox(yk, current_step_size * alpha, *g_prox_args)
        grad_fk = f_prime(xk)
        z = h_prox(2 * xk - yk - current_step_size * grad_fk, current_step_size * beta, *h_prox_args)
        incr = z - xk
        if backtracking:
            fx = f(xk)
            for _ in range(max_iter_backtracking):
                if f(z) <= fx + grad_fk.dot(incr) + incr.dot(incr) / (2.0 * current_step_size):
                    # step size found
                    break
                else:
                    current_step_size *= backtracking_factor
                    z = h_prox(2 * xk - yk - current_step_size * grad_fk, current_step_size * beta, *h_prox_args)
                    incr = z - xk
            else:
                warnings.warn("Maxium number of line-search iterations reached")
        yk += incr

        norm_increment = linalg.norm(incr, np.inf)
        if verbose > 0:
            print("Iteration %s, prox-grad norm: %s" % (it, norm_increment / current_step_size))

        if norm_increment < tol * current_step_size:
            success = True
            if verbose:
                print("Achieved relative tolerance at iteration %s" % it)
            break

        if callback is not None:
            callback(xk)
        if it >= max_iter:
            warnings.warn(
                "three_split did not reach the desired tolerance level",
                RuntimeWarning)
        it += 1

    return optimize.OptimizeResult(
        x=yk, success=success,
        jac=incr / current_step_size,  # prox-grad mapping
        nit=it)



def primal_dual(f, f_prime, g_prox, h_prox, L, x0, alpha=1.0, beta=1.0, tol=1e-12,
                max_iter=10000, verbose=0, callback=None, step_size_x=1e-3,
                step_size_y=1e3, max_iter_ls=20, g_prox_args=(), h_prox_args=()):
    """
    !WARNING!: this is a work in progress algorithm, not stable at all.

    proximal gradient-descent solver for optimization problems of the form

                       minimize_x f(x) + alpha * g(x) + beta * h(L x)

    where f is a smooth function and g is a (possibly non-smooth)
    function for which the proximal operator is known.

    Parameters
    ----------
    f : callable
        f(x) returns the value of f at x.

    f_prime : callable
        f_prime(x) returns the gradient of f.

    g_prox : callable of the form g_prox(x, alpha)
        g_prox(x, alpha) returns the proximal operator of g at x
        with parameter alpha.

    x0 : array-like
        Initial guess

    L : ndarray or sparse matrix
        Linear operator inside the h term.

    max_iter : int
        Maximum number of iterations.

    verbose : int
        Verbosity level, from 0 (no output) to 2 (output on each iteration)

    callback : callable
        callback function (optional).

    Returns
    -------
    res : OptimizeResult
        The optimization result represented as a
        ``scipy.optimize.OptimizeResult`` object. Important attributes are:
        ``x`` the solution array, ``success`` a Boolean flag indicating if
        the optimizer exited successfully and ``message`` which describes
        the cause of the termination. See `scipy.optimize.OptimizeResult`
        for a description of other attributes.

    References
    ----------
    Chambolle, Antonin, and Thomas Pock. "On the ergodic convergence rates of a
    first-order primal-dual algorithm." Mathematical Programming (2015)
    """
    xk = np.array(x0, copy=True)
    yk = L.dot(xk)
    success = False
    if not max_iter_ls > 0:
        raise ValueError('Line search iterations need to be greater than 0')

    if g_prox is None:
        def g_prox(x, step_size, *args): return x
    if h_prox is None:
        def h_prox(x, step_size, *args): return x

    # conjugate of h_prox
    def h_prox_conj(x, step_size, *args):
        return x - step_size * h_prox(x / step_size,  beta / step_size, *args)
    it = 1
    # .. main iteration ..
    while it < max_iter:

        grad_fk = f_prime(xk)
        x_next = g_prox(xk - step_size_x * grad_fk - step_size_x * L.T.dot(yk),
                        step_size_x * alpha, *g_prox_args)
        y_next = h_prox_conj(yk + step_size_y * L.dot(2 * x_next - xk),
                             step_size_y, *h_prox_args)

        incr = linalg.norm(x_next - xk) ** 2 + linalg.norm(y_next - yk) ** 2
        yk = y_next
        xk = x_next

        if verbose > 0:
            print("Iteration %s, increment: %s" % (it, incr))

        if callback is not None:
            callback(xk)

        if incr < tol:
            if verbose:
                print("Achieved relative tolerance at iteration %s" % it)
            success = True
            break

        it += 1

    if it >= max_iter:
        warnings.warn(
            "proximal_gradient did not reach the desired tolerance level", RuntimeWarning)

    return optimize.OptimizeResult(
        x=xk, success=success,
        nit=it)