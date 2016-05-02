import os
import sys
import theano
import theano.tensor as T
from theano.tensor.shared_randomstreams import RandomStreams
import cPickle
import gzip
import numpy
import timeit
from PIL import Image

from cutils.trainer import sgd
from cutils.utils import tile_raster_images

# Include current path in the pythonpath
script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(script_path)

from stacked_autoencoder import SdA


def load_data(dataset_location):
    # Load the dataset
    dataset_location = sys.argv[1]
    f = gzip.open(dataset_location, "rb")
    try:
        train_set, valid_set, test_set = cPickle.load(f, encoding="latin1")
    except:
        train_set, valid_set, test_set = cPickle.load(f)
    f.close()

    def shared_dataset(data_xy, borrow=True):
        """ Load the dataset into shared variables """
        data_x, data_y = data_xy
        assert len(data_x) == len(data_y)
        shared_x = theano.shared(numpy.asarray(data_x,
                                               dtype=theano.config.floatX),
                                 borrow=borrow)
        shared_y = theano.shared(numpy.asarray(data_y,
                                               dtype=theano.config.floatX),
                                 borrow=borrow)
        # Cast the labels as int32, so that they can be used as indices
        return shared_x, T.cast(shared_y, 'int32')

    train_set_x, train_set_y = shared_dataset(train_set)
    valid_set_x, valid_set_y = shared_dataset(valid_set)
    test_set_x, test_set_y = shared_dataset(test_set)

    rval = [(train_set_x, train_set_y), (valid_set_x, valid_set_y),
            (test_set_x, test_set_y)]
    return rval


def sgd_optimization_mnist_sda(learning_rate=0.1, n_epochs=15,
                              dataset='mnist.pkl.gz', batch_size=20):
    # Initialize the stacked autoencoder
    numpy_rng = numpy.random.RandomState(89677)
    print("... Building the model")
    sda = SdA(
        numpy_rng=numpy_rng,
        n_ins=28 * 28,
        hidden_layers_sizes=[1000, 1000, 1000],
        n_outs=10)

    # Implement pretraining first
    print("... fetching the pretraining functions")
    pretraining_fns = sda.pretraining_functions(
        train_set_x=train_set_x,
        train_set_y=train_set_y)
    print("... pretraining the model")
    start_time = timeit.default_timer()
    # Do layer wise pre-training
    corruption_levels = [.1, .2, .3]
    for i in range(sda.n_layers):
        # Run training for pretraining_epochs
        for epoch in pretraining_epochs:
            c = []
            for batch_index in range(n_train_batches):
                c.append(pretraining_fns[i](index=batch_index,
                         corruption=corruption_levels[i],
                         lr=pretrain_lr))

            print('Pre-training layer %i, epoch %d, cost %f'
                  % (i, epoch, numpy.mean(c)))

    end_time = timeit.default_timer()
    pretraining_time = end_time - start_time
    print('The pretraining code for file ' +
          os.path.split(__file__)[1] +
          ' ran for %.2fm' % ((pretraining_time) / 60.))

    ################
    # TRAIN MODEL  #
    ################
    print("... Training the model")
    # Early stopping parameters
    patience = 10000  # Look at these many parameters regardless
    # Increase patience by this quantity when a best score is achieved
    patience_increase = 2
    improvement_threshold = 0.995  # Minimum significant improvement
    validation_frequency = min(n_train_batches, patience // 2)
    best_validation_loss = numpy.inf
    test_score = 0.
    start_time = timeit.default_timer()

    done_looping = False
    epoch = 0
    while (epoch < n_epochs) and (not done_looping):
        epoch = epoch + 1
        for minibatch_index in range(n_train_batches):
            minibatch_avg_cost = train_model(minibatch_index)
            # Iteration number
            iter = (epoch - 1) * n_train_batches + minibatch_index
            # Check if validation needs to be performed
            if (iter + 1) % validation_frequency == 0:
                # Compute average 0-1 loss on validation set
                validation_losses = [validate_model(i)
                                     for i in range(n_valid_batches)]
                this_validation_loss = numpy.mean(validation_losses)

                print(
                    'epoch %i, minibatch %i/%i, validation error %f %%' %
                    (
                        epoch,
                        minibatch_index + 1,
                        n_train_batches,
                        this_validation_loss * 100.
                    )
                )

                # Check if this is the best validation score
                if this_validation_loss < best_validation_loss:
                    # Increase patience if gain is gain is significant
                    if this_validation_loss < best_validation_loss * \
                            improvement_threshold:
                        patience = max(patience, iter * patience_increase)

                    best_validation_loss = this_validation_loss

                    # Get test scores
                    test_losses = [test_model(i) for i
                                   in range(n_test_batches)]
                    test_score = numpy.mean(test_losses)

                    print(
                        'epoch %i, minibatch %i/%i, test error of'
                        ' best model %f %%' %
                        (
                            epoch,
                            minibatch_index + 1,
                            n_train_batches,
                            test_score * 100.
                        )
                    )

        if patience <= iter:
            done_looping = True
            break
    end_time = timeit.default_timer()
    print(
        (
            'Optimization complete with best validation error of %f %%,'
            'with test error of %f %%'
        )
        % (best_validation_loss * 100., test_score * 100.)
    )
    print ('The code run for %d epochs, with %f epochs/sec' % (
        epoch, 1. * epoch / (end_time - start_time)))


if __name__ == '__main__':
    sgd_optimization_mnist_sda(dataset=sys.argv[1])
