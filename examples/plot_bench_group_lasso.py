"""
Total variation regularization
==============================

Comparison of solvers with total variation regularization.

TODO: split computational and plotting code
"""
import numpy as np
from scipy import misc
from scipy.sparse import linalg as splinalg
from scipy.ndimage import gaussian_filter as gf
import pylab as plt
import copt as cp

np.random.seed(0)

# .. generate some data ..


img = misc.face(gray=True).astype(np.float)
img = misc.imresize(img, 0.1)

n_rows, n_cols = img.shape
n_features = n_rows * n_cols
n_samples = n_features
max_iter = 1000
print('#features', n_features)

kernel_width = 5
A = splinalg.LinearOperator(
    matvec=lambda x: gf(x.reshape(img.shape), kernel_width),
    rmatvec=lambda x: gf(x.reshape(img.shape), kernel_width),
    dtype=np.float, shape=(n_features, n_features))

b = A.matvec(img.ravel()) + np.random.randn(n_samples)

np.random.seed(0)
n_samples = n_features

# .. compute the step-size ..
s = splinalg.svds(A, k=1, return_singular_vectors=False,
                  tol=1e-3, maxiter=500)[0]
alpha = 0 / n_samples
step_size = cp.utils.get_step_size(A, 'square', alpha)
f_grad = cp.utils.squareloss(A, b, alpha)


def loss(x, beta):
    img = x.reshape((n_rows, n_cols))
    tmp1 = np.abs(np.diff(img, axis=0))
    tmp2 = np.abs(np.diff(img, axis=1))
    return f_grad(x)[0] + beta * (tmp1.sum() + tmp2.sum())


# .. run the solver for different values ..
# .. of the regularization parameter beta ..
all_betas = [0, 1e-6, 1e-5, 1e-4]
all_trace_ls, all_trace_nols, all_trace_pdhg, out_img = [], [], [], []
all_trace_ls_time, all_trace_nols_time, all_trace_pdhg_time = [], [], []
for i, beta in enumerate(all_betas):

    def g_prox(x, step_size):
        return cp.tv_prox.prox_tv1d_cols(
            step_size * beta, x, n_rows, n_cols)


    def h_prox(x, step_size):
        return cp.tv_prox.prox_tv1d_rows(
            step_size * beta, x, n_rows, n_cols)

    cb_tosls = cp.utils.Trace()
    x0 = np.zeros(n_features)
    cb_tosls(x0)
    tos_ls = cp.minimize_TOS(
        f_grad, x0, g_prox, h_prox,
        step_size=2 * step_size,
        max_iter=max_iter, tol=1e-14, verbose=1,
        callback=cb_tosls)
    trace_ls = np.array([loss(x, beta) for x in cb_tosls.trace_x])
    all_trace_ls.append(trace_ls)
    all_trace_ls_time.append(cb_tosls.trace_time)
    out_img.append(tos_ls.x.reshape(img.shape))

    cb_tos = cp.utils.Trace()
    x0 = np.zeros(n_features)
    cb_tos(x0)
    tos = cp.minimize_TOS(
        f_grad, x0, g_prox, h_prox,
        step_size=step_size,
        max_iter=int(1.5 * max_iter), tol=1e-14, verbose=1,
        line_search=False, callback=cb_tos)
    trace_nols = np.array([loss(x, beta) for x in cb_tos.trace_x])
    all_trace_nols.append(trace_nols)
    all_trace_nols_time.append(cb_tos.trace_time)

    cb_pdhg = cp.utils.Trace()
    x0 = np.zeros(n_features)
    cb_pdhg(x0)
    pdhg_nols = cp.gradient.minimize_PDHG(
        f_grad, x0, g_prox, h_prox,
        callback=cb_pdhg, verbose=2, max_iter=max_iter,
        step_size=step_size,
        step_size2=(1./step_size) / 2, tol=0, line_search=True)
    trace_pdhg = np.array([loss(x, beta) for x in cb_pdhg.trace_x])
    all_trace_pdhg.append(trace_pdhg)
    all_trace_pdhg_time.append(cb_pdhg.trace_time)

# .. plot the results ..
f, ax = plt.subplots(2, 4, sharey=False)
xlim = [0.02, 0.02, 0.1]
for i, beta in enumerate(all_betas):
    ax[0, i].set_title(r'$\lambda=%s$' % beta)
    ax[0, i].imshow(out_img[i],
                    interpolation='nearest', cmap=plt.cm.gray)
    ax[0, i].set_xticks(())
    ax[0, i].set_yticks(())

    fmin = min(np.min(all_trace_ls[i]), np.min(all_trace_nols[i]))
    scale = all_trace_ls[i][0] - fmin
    plot_tos, = ax[1, i].plot(
        (all_trace_ls[i] - fmin) / scale,
        lw=4, marker='o', markevery=100,
        markersize=10)

    plot_nols, = ax[1, i].plot(
        (all_trace_nols[i] - fmin) / scale,
        lw=4, marker='h', markevery=100,
        markersize=10)

    plot_pdhg, = ax[1, i].plot(
        (all_trace_pdhg[i] - fmin) / scale,
        lw=4, marker='^', markevery=100,
        markersize=10)

    ax[1, i].set_xlabel('Iterations')
    ax[1, i].set_yscale('log')
    ax[1, i].set_ylim((1e-14, None))
    ax[1, i].grid(True)


plt.gcf().subplots_adjust(bottom=0.15)
plt.figlegend(
    (plot_tos, plot_nols, plot_pdhg),
    ('TOS with line search', 'TOS without line search', 'PDHG'), ncol=5,
    scatterpoints=1,
    loc=(-0.00, -0.0), frameon=False,
    bbox_to_anchor=[0.05, 0.01])

ax[1, 0].set_ylabel('Objective minus optimum')
plt.show()
