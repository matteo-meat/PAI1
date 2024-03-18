import torch
import numpy as np
from loss import residual_loss, ic_loss
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
import os

losses = []  # To store losses
name = "output"
current_file = os.path.abspath(__file__)
output_dir = os.path.join(os.path.dirname(current_file), name)

model_dir = os.path.join(output_dir, "model")
if not os.path.exists(model_dir):
    os.makedirs(model_dir)

file_path = f"{output_dir}/train.txt"


def train(model, epochs, batchsize, optimizer, pde_fn, ic_fns, domaindataset, icdataset):
    dataloader = DataLoader(domaindataset, batch_size=batchsize,shuffle=True,num_workers = 0,drop_last = False)
    ic_dataloader = DataLoader(icdataset, batch_size=batchsize, shuffle=True, num_workers = 0, drop_last = False)
    model.train(True)
    # Open the log file for writing
    with open(file_path, "w") as log_file:
        for epoch in range(epochs):
            for batch_idx, (x_in) in enumerate(dataloader):          
                (x_ic) = next(iter(ic_dataloader))
                #print(f"{x_in}, {x_ic}")
                x_in = torch.Tensor(x_in).to(torch.device('cuda:0'))
                x_ic = torch.Tensor(x_ic).to(torch.device('cuda:0'))
                loss_eqn = residual_loss(x_in, model, pde_fn)
                loss = loss_eqn
                for i in range(len(ic_fns)):
                    loss_ic = ic_loss(x_ic, model, ic_fns[i])
                    loss += loss_ic
                #loss.requires_grad = True
                optimizer.zero_grad()
                loss.backward()
        
                optimizer.step() 
                if batch_idx % 10 ==0:
                    print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.10f}'.format(
                        epoch, batch_idx, int(len(dataloader.dataset)/batchsize),
                        100. * batch_idx / len(dataloader), loss.item()))
                    
                    # Save to log file
                    log_file.write('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.10f}\n'.format(
                        epoch, batch_idx, int(len(dataloader.dataset)/batchsize),
                        100. * batch_idx / len(dataloader), loss.item()))
                    
                    losses.append(loss.item())  # Storing the loss

        # Save the model
    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss,
        }, os.path.join(model_dir, 'model.pth'))
    
    plt.plot(losses)
    plt.xlabel('Iterations')
    plt.ylabel('Loss')
    plt.title('Training Loss')
    plt.savefig(f'{output_dir}/training_loss.png')
    plt.show()